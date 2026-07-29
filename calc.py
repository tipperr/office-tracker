"""
Calendar utilities and business logic for office tracking.
Pure functions for math calculations and date handling.
"""

import calendar
import json
from datetime import date, timedelta
from typing import Dict, List, Optional, Any
import holidays
from decimal import Decimal, ROUND_HALF_UP


def _normalize_country(country: str | None) -> str:
    """Normalize country code to standard format."""
    if not country:
        return "US"
    aliases = {"UnitedStates": "US", "USA": "US", "US": "US"}
    return aliases.get(str(country), str(country))


def build_holidays(year: int, country: str | None, state: str | None):
    """
    Returns a holidays object for the year.
    Only passes subdiv when state is truthy; treats '' as None.
    """
    c = _normalize_country(country)
    subdiv = state or None  # '' -> None
    try:
        if subdiv:
            return holidays.country_holidays(c, years=year, subdiv=subdiv)
        return holidays.country_holidays(c, years=year)
    except Exception:
        # Fallback if state code is invalid: ignore subdiv
        return holidays.country_holidays(c, years=year)


def month_grid(year: int, month: int) -> List[List[Optional[date]]]:
    """
    Generate a calendar grid for the given month.
    
    Args:
        year: Year (e.g., 2024)
        month: Month (1-12)
        
    Returns:
        List of weeks, each containing 7 days (None for empty cells)
    """
    cal = calendar.monthcalendar(year, month)
    grid = []
    
    for week in cal:
        week_dates = []
        for day in week:
            if day == 0:
                week_dates.append(None)
            else:
                week_dates.append(date(year, month, day))
        grid.append(week_dates)
    
    return grid


def credited_holiday(holiday_date: date, settings: Dict[str, Any]) -> bool:
    """
    Determine if a holiday should be credited based on settings.
    
    Args:
        holiday_date: Date of the holiday
        settings: User settings dictionary
        
    Returns:
        True if holiday should be credited to numerator
    """
    weekday = holiday_date.strftime('%a').upper()  # MON, TUE, etc.
    
    # Check if it's a credited weekday (Tue/Wed/Thu by default)
    if weekday in settings.get('credit_weekdays', ['TUE', 'WED', 'THU']):
        return True
    
    # Handle Mon/Fri based on treatment setting
    if weekday in ['MON', 'FRI']:
        treatment = settings.get('monfri_holiday_treatment', 'neutral')
        return treatment == 'credit'
    
    return False


# Work-mode categories used by the monthly formula. The older, more specific
# BIOHUB and TRAINING statuses remain valid offsite-work entries.
IN_PERSON_WORK_STATUSES = {"IN_OFFICE", "OFFSITE_WORK", "BIOHUB", "TRAINING"}
PTO_STATUSES = {"VACATION", "SICK", "VOLUNTEER"}
COMPANY_HOLIDAY_STATUSES = {"COMPANY_HOLIDAY", "OTHER_HOLIDAY"}


def compute_summary(days: List[Dict[str, Any]], settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute monthly work-mode statistics.

    In-person work percentage =
        (in-person/offsite work days + PTO days + company holidays)
        / weekdays in the month

    A date can contribute at most one credit. This prevents a PTO day that also
    falls on a company holiday from being counted twice.
    
    Args:
        days: List of day records for the month
        settings: User settings dictionary
        
    Returns:
        Dictionary with the formula inputs and requirement progress.
    """
    if days:
        month_date = days[0]['date']
        _, days_in_month = calendar.monthrange(month_date.year, month_date.month)
        workdays = sum(
            1
            for day_number in range(1, days_in_month + 1)
            if date(month_date.year, month_date.month, day_number).weekday() < 5
        )
    else:
        workdays = 0

    status_counts = {}
    in_person_work_days = 0
    pto_days = 0
    company_holidays = 0
    
    for day in days:
        status = day.get('status', 'NONE')
        status_counts[status] = status_counts.get(status, 0) + 1

        is_weekday = day['date'].weekday() < 5

        # In-person and offsite work retain the existing weekend-credit
        # behavior. PTO and company holidays only count on weekdays.
        if status in IN_PERSON_WORK_STATUSES:
            in_person_work_days += 1
        elif is_weekday and status in PTO_STATUSES:
            pto_days += 1
        elif is_weekday and (
            day.get('is_holiday', False)
            or status in COMPANY_HOLIDAY_STATUSES
        ):
            company_holidays += 1

    numerator = in_person_work_days + pto_days + company_holidays
    denominator = workdays
    
    # Calculate required days using specified rounding
    required_percent = settings.get('required_percent', 0.60)
    rounding_mode = settings.get('rounding_mode', 'ceil')
    
    if denominator > 0:
        required_exact = required_percent * denominator
        
        if rounding_mode == 'ceil':
            import math
            required_days = math.ceil(required_exact)
        elif rounding_mode == 'floor':
            import math
            required_days = math.floor(required_exact)
        else:  # round_half_up
            required_days = int(Decimal(str(required_exact)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        
        percent_achieved = (numerator / denominator) * 100 if denominator > 0 else 0
    else:
        required_days = 0
        percent_achieved = 0
    
    balance = numerator - required_days
    
    return {
        'workdays': workdays,
        'denominator': denominator,
        'numerator': numerator,
        'required_days': required_days,
        'balance': balance,
        'percent_achieved': percent_achieved,
        'status_counts': status_counts,
        'in_person_work_days': in_person_work_days,
        'pto_days': pto_days,
        'company_holidays': company_holidays,
        # Retained for older export consumers.
        'credited_holidays': company_holidays
    }


def serialize_month(days: List[Dict[str, Any]], settings: Dict[str, Any], summary: Dict[str, Any]) -> str:
    """
    Serialize month data to JSON for export/API use.
    Stable schema for future ESP32/CLI clients.
    
    Args:
        days: List of day records
        settings: User settings
        summary: Computed summary statistics
        
    Returns:
        JSON string with stable schema
    """
    # Convert days to serializable format
    serialized_days = []
    for day in days:
        serialized_days.append({
            'date': day['date'].isoformat(),
            'status': day['status'],
            'is_holiday': day['is_holiday'],
            'holiday_name': day.get('holiday_name', ''),
            'notes': day.get('notes', '')
        })
    
    # Create stable export format
    export_data = {
        'version': '1.3',  # Work-mode formula and explicit PTO categories
        'user_id': settings.get('user_id', 'rachel'),
        'month': {
            'year': days[0]['date'].year if days else None,
            'month': days[0]['date'].month if days else None
        },
        'settings': {
            'required_percent': settings.get('required_percent', 0.60),
            'rounding_mode': settings.get('rounding_mode', 'ceil'),
            'credit_weekdays': settings.get('credit_weekdays', ['TUE', 'WED', 'THU']),
            'monfri_holiday_treatment': settings.get('monfri_holiday_treatment', 'neutral'),
            'country': settings.get('country', 'UnitedStates'),
            'state': settings.get('state', ''),
            'timezone': settings.get('timezone', 'America/Los_Angeles')
        },
        'summary': summary,
        'days': serialized_days
    }
    
    return json.dumps(export_data, indent=2, default=str)


def deserialize_month(json_data: str) -> Dict[str, Any]:
    """
    Deserialize month data from JSON for import.
    
    Args:
        json_data: JSON string to deserialize
        
    Returns:
        Dictionary with days, settings, and summary
    """
    try:
        data = json.loads(json_data)
        
        # Convert date strings back to date objects
        for day in data.get('days', []):
            day['date'] = date.fromisoformat(day['date'])
        
        return {
            'days': data.get('days', []),
            'settings': data.get('settings', {}),
            'summary': data.get('summary', {}),
            'version': data.get('version', '1.0')
        }
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        raise ValueError(f"Invalid JSON format: {e}")


def get_weekday_name(day_date: date) -> str:
    """Get abbreviated weekday name (MON, TUE, etc.)."""
    return day_date.strftime('%a').upper()


def is_weekend(day_date: date) -> bool:
    """Check if date is a weekend (Saturday or Sunday)."""
    return day_date.weekday() >= 5


def get_status_color(status: str) -> str:
    """Get color for status display."""
    colors = {
        'NONE': '#ffffff',
        'WFH': '#f5f5f5',
        'IN_OFFICE': '#e3f2fd',
        'VACATION': '#fff3e0',
        'SICK': '#fff3e0',
        'VOLUNTEER': '#fff3e0',
        'OFFSITE_WORK': '#e3f2fd',
        'BIOHUB': '#e3f2fd',
        'TRAINING': '#e3f2fd',
        'COMPANY_HOLIDAY': '#e3f2fd',
        'OTHER_HOLIDAY': '#e3f2fd'
    }
    return colors.get(status, '#ffffff')


def get_status_emoji(status: str) -> str:
    """Get emoji for status display."""
    emojis = {
        'NONE': '',
        'WFH': '🏠',
        'IN_OFFICE': '🏢',
        'VACATION': '🏖️',
        'SICK': '🤒',
        'VOLUNTEER': '🤝',
        'OFFSITE_WORK': '📍',
        'BIOHUB': '🏢',
        'TRAINING': '🏢',
        'COMPANY_HOLIDAY': '🎉',
        'OTHER_HOLIDAY': '🏢'
    }
    return emojis.get(status, '')


def get_next_status(current_status: str) -> str:
    """Get the next selectable work mode."""
    if current_status == 'OTHER_HOLIDAY':
        current_status = 'COMPANY_HOLIDAY'
    cycle = [
        'NONE', 'WFH', 'IN_OFFICE', 'OFFSITE_WORK', 'VACATION', 'SICK',
        'VOLUNTEER', 'BIOHUB', 'TRAINING', 'COMPANY_HOLIDAY'
    ]
    try:
        current_index = cycle.index(current_status)
        return cycle[(current_index + 1) % len(cycle)]
    except ValueError:
        return 'NONE'


def validate_date_range(start_date: date, end_date: date) -> bool:
    """Validate that date range is reasonable."""
    if start_date > end_date:
        return False
    
    # Limit to reasonable ranges (e.g., max 1 year)
    if (end_date - start_date).days > 365:
        return False
    
    return True


def get_month_name(month: int) -> str:
    """Get full month name from month number."""
    return calendar.month_name[month]


def add_months(source_date: date, months: int) -> date:
    """Add months to a date, handling edge cases."""
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1
    day = min(source_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)
