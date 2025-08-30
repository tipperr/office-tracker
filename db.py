"""
Database helpers for Supabase integration.
Handles CRUD operations and schema initialization.
"""

import json
from datetime import date, datetime
from typing import Dict, List, Optional, Any
from supabase import create_client, Client
import streamlit as st

import os
import streamlit as st

def get_secret(name: str, default=None):
    # prefer Streamlit secrets, fallback to env vars
    try:
        return st.secrets[name]
    except Exception:
        return os.getenv(name, default)


def get_supabase_client() -> Client:
    """Initialize and return Supabase client using Streamlit secrets."""
    '''url = st.secrets["SUPABASE_URL"] 
    key = st.secrets["SUPABASE_SERVICE_KEY"]'''
    url = get_secret("SUPABASE_URL")
    key = get_secret("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL / SUPABASE_SERVICE_KEY.")
    return create_client(url, key)


def init_schema_if_needed() -> None:
    """
    Verify tables exist and create if missing.
    Note: This uses the service key to create tables.
    """
    supabase = get_supabase_client()
    
    # Check if tables exist by trying to query them
    try:
        supabase.table('settings').select('id').limit(1).execute()
        supabase.table('days').select('id').limit(1).execute()
        print("Tables already exist")
    except Exception as e:
        print(f"Tables don't exist or error occurred: {e}")
        print("Please run the DDL commands from README.md manually in your Supabase SQL editor")
        # TODO: Implement automatic table creation via RPC if needed


def get_settings(user_id: str = 'rachel') -> Dict[str, Any]:
    """
    Get user settings, creating default if none exist.
    
    Args:
        user_id: User identifier (defaults to 'rachel' for v1)
        
    Returns:
        Dictionary containing user settings
    """
    supabase = get_supabase_client()
    
    try:
        result = supabase.table('settings').select('*').eq('user_id', user_id).execute()
        
        if result.data:
            settings = result.data[0]
            # Parse JSON field
            settings['credit_weekdays'] = json.loads(settings['credit_weekdays_json'])
            return settings
        else:
            # Create default settings
            default_settings = {
                'user_id': user_id,
                'required_percent': 0.60,
                'rounding_mode': 'ceil',
                'credit_weekdays_json': json.dumps(['TUE', 'WED', 'THU']),
                'monfri_holiday_treatment': 'neutral',
                #Not needed for change to Render:
                #'country': st.secrets.get('DEFAULT_COUNTRY', 'UnitedStates'),
                #'state': st.secrets.get('DEFAULT_STATE', ''),
                #'timezone': st.secrets.get('TIMEZONE', 'America/Los_Angeles')
                #For change to Render:
                'country':  get_secret('DEFAULT_COUNTRY', 'UnitedStates'),
                'state':    get_secret('DEFAULT_STATE', ''),
                'timezone': get_secret('TIMEZONE', 'America/Los_Angeles')
            }
            
            result = supabase.table('settings').insert(default_settings).execute()
            settings = result.data[0]
            settings['credit_weekdays'] = json.loads(settings['credit_weekdays_json'])
            return settings
            
    except Exception as e:
        st.error(f"Error getting settings: {e}")
        # Return default settings as fallback
        return {
            'user_id': user_id,
            'required_percent': 0.60,
            'rounding_mode': 'ceil',
            'credit_weekdays': ['TUE', 'WED', 'THU'],
            'monfri_holiday_treatment': 'neutral',
            'country': 'UnitedStates',
            'state': '',
            'timezone': 'America/Los_Angeles'
        }


def upsert_settings(user_id: str, fields: Dict[str, Any]) -> None:
    """
    Update user settings.
    
    Args:
        user_id: User identifier
        fields: Dictionary of fields to update
    """
    supabase = get_supabase_client()
    
    try:
        # Convert credit_weekdays list to JSON if present
        if 'credit_weekdays' in fields:
            fields['credit_weekdays_json'] = json.dumps(fields['credit_weekdays'])
            del fields['credit_weekdays']
        
        # Try to update existing record
        result = supabase.table('settings').update(fields).eq('user_id', user_id).execute()
        
        if not result.data:
            # If no record was updated, insert new one
            fields['user_id'] = user_id
            supabase.table('settings').insert(fields).execute()
            
    except Exception as e:
        st.error(f"Error updating settings: {e}")


def get_month_days(user_id: str, year: int, month: int) -> List[Dict[str, Any]]:
    """
    Get all days for a specific month, auto-seeding if empty.
    Includes lazy backfill for missing weekend dates.
    
    Args:
        user_id: User identifier
        year: Year (e.g., 2024)
        month: Month (1-12)
        
    Returns:
        List of day records for the month
    """
    supabase = get_supabase_client()
    
    try:
        # Query existing days for the month
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        
        result = supabase.table('days').select('*').eq('user_id', user_id).gte('date', start_date.isoformat()).lt('date', end_date.isoformat()).execute()
        
        if result.data:
            # Convert date strings back to date objects
            for day in result.data:
                day['date'] = datetime.fromisoformat(day['date']).date()
            
            # Check for missing weekend dates and backfill if needed
            existing_dates = {day['date'] for day in result.data}
            missing_dates = []
            
            from calc import month_grid
            import holidays
            
            # Get all calendar dates for the month
            grid = month_grid(year, month)
            settings = get_settings(user_id)
            country_holidays = holidays.country_holidays(settings['country'], state=settings.get('state'))
            
            for week in grid:
                for day_date in week:
                    if day_date and day_date not in existing_dates:
                        # Missing date - create record
                        is_holiday = day_date in country_holidays
                        holiday_name = country_holidays.get(day_date, '') if is_holiday else ''
                        
                        missing_record = {
                            'user_id': user_id,
                            'date': day_date.isoformat(),
                            'status': 'NONE',
                            'is_holiday': is_holiday,
                            'holiday_name': holiday_name,
                            'notes': ''
                        }
                        missing_dates.append(missing_record)
            
            # Insert missing dates if any
            if missing_dates:
                insert_result = supabase.table('days').insert(missing_dates).execute()
                # Add to result data
                for day in insert_result.data:
                    day['date'] = datetime.fromisoformat(day['date']).date()
                    result.data.append(day)
            
            return result.data
        else:
            # Auto-seed the month
            return _seed_month(user_id, year, month)
            
    except Exception as e:
        st.error(f"Error getting month days: {e}")
        return []


def _seed_month(user_id: str, year: int, month: int) -> List[Dict[str, Any]]:
    """
    Seed a month with default day records (all calendar days Mon-Sun).
    For user_id='rachel', preset Mon/Fri → WFH, Tue/Wed/Thu → IN_OFFICE.
    Weekends default to NONE.
    
    Args:
        user_id: User identifier
        year: Year
        month: Month
        
    Returns:
        List of created day records
    """
    from calc import month_grid, credited_holiday
    import holidays
    
    supabase = get_supabase_client()
    settings = get_settings(user_id)
    
    # Get holidays for the year
    country_holidays = holidays.country_holidays(settings['country'], state=settings.get('state'))
    
    # Generate all days in the month
    grid = month_grid(year, month)
    days_to_insert = []
    
    for week in grid:
        for day_date in week:
            if day_date:  # Include all calendar days (Mon-Sun)
                is_holiday = day_date in country_holidays
                holiday_name = country_holidays.get(day_date, '') if is_holiday else ''
                
                # Set default status based on weekday for user_id='rachel'
                default_status = 'NONE'
                if user_id == 'rachel' and day_date.weekday() < 5:  # Only set defaults for weekdays
                    weekday = day_date.weekday()  # Monday=0, Friday=4
                    if weekday in [0, 4]:  # Mon/Fri
                        default_status = 'WFH'
                    elif weekday in [1, 2, 3]:  # Tue/Wed/Thu
                        default_status = 'IN_OFFICE'
                
                day_record = {
                    'user_id': user_id,
                    'date': day_date.isoformat(),
                    'status': default_status,
                    'is_holiday': is_holiday,
                    'holiday_name': holiday_name,
                    'notes': ''
                }
                days_to_insert.append(day_record)
    
    try:
        if days_to_insert:
            result = supabase.table('days').insert(days_to_insert).execute()
            # Convert date strings back to date objects
            for day in result.data:
                day['date'] = datetime.fromisoformat(day['date']).date()
            return result.data
        return []
    except Exception as e:
        st.error(f"Error seeding month: {e}")
        return []


def upsert_day(user_id: str, day_date: date, fields: Dict[str, Any]) -> None:
    """
    Update or insert a day record.
    
    Args:
        user_id: User identifier
        day_date: Date of the day
        fields: Fields to update
    """
    supabase = get_supabase_client()
    
    try:
        # Try to update existing record
        result = supabase.table('days').update(fields).eq('user_id', user_id).eq('date', day_date.isoformat()).execute()
        
        if not result.data:
            # If no record was updated, insert new one
            fields.update({
                'user_id': user_id,
                'date': day_date.isoformat()
            })
            supabase.table('days').insert(fields).execute()
            
    except Exception as e:
        st.error(f"Error updating day: {e}")


#def bulk_set_vacation(user_id: str, start_date: date, end_date: date) -> None:
    """
    Set status to VACATION for a date range (weekdays only).
    
    Args:
        user_id: User identifier
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
    """
    """
    supabase = get_supabase_client()
    
    try:
        # Update all weekdays in the range
        result = supabase.table('days').update({'status': 'VACATION'}).eq('user_id', user_id).gte('date', start_date.isoformat()).lte('date', end_date.isoformat()).execute()
        
        # Also ensure days exist for the range (in case they span multiple months)
        from datetime import timedelta
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() < 5:  # Weekday
                upsert_day(user_id, current_date, {'status': 'VACATION'})
            current_date += timedelta(days=1)
            
    except Exception as e:
        st.error(f"Error setting vacation range: {e}")
"""

def bulk_set_vacation(user_id: str, start_date: date, end_date: date) -> int:
    """
    Set status = 'VACATION' for all days in [start_date, end_date] inclusive.
    Returns number of rows affected (best-effort).
    """
    supabase = get_supabase_client()
    try:
        result = (
            supabase
            .table('days')
            .update({'status': 'VACATION'})
            .eq('user_id', user_id)
            .gte('date', start_date.isoformat())
            .lte('date', end_date.isoformat())
            .execute()
        )
        # Supabase may not return affected row count reliably; fall back to 0/len
        return len(result.data) if getattr(result, "data", None) else 0
    except Exception as e:
        # Streamlit-safe error; don't crash the app
        import streamlit as st
        st.error(f"Error setting vacation range: {e}")
        return 0
