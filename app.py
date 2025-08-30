"""
Streamlit web app for office tracking.
Main UI with calendar view, sidebar controls, and month navigation.
"""

import streamlit as st
import json
from datetime import date, datetime, timedelta
from typing import Dict, List, Any
import calendar

# Import our modules
import db
import calc

# TODO(auth): Switch to Supabase Auth, enable RLS, add user_id from auth context
# TODO(device): Expose /api/month?year=YYYY&month=MM via FastAPI for ESP32 clients

# Page configuration
st.set_page_config(
    page_title="Desk-O-Meter",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
.day-cell { position:relative; border-radius:12px; }
.day-number {
  position:absolute; top:.4rem; left:.55rem;
  font-weight:700; font-size:16px;
  color:#e5e7eb;                /* high-contrast for dark theme */
  text-shadow:0 1px 2px rgba(0,0,0,.6);
  z-index: 2;                   /* sits above widgets */
}
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'current_year' not in st.session_state:
    today = date.today()
    st.session_state.current_year = today.year
    st.session_state.current_month = today.month

if 'user_id' not in st.session_state:
    st.session_state.user_id = 'rachel'  # Default user for v1


def load_month_data():
    """Load data for the current month."""
    try:
        # Initialize schema if needed
        db.init_schema_if_needed()
        
        # Get settings and days
        settings = db.get_settings(st.session_state.user_id)
        days = db.get_month_days(
            st.session_state.user_id,
            st.session_state.current_year,
            st.session_state.current_month
        )
        
        # Compute summary
        summary = calc.compute_summary(days, settings)
        
        return settings, days, summary
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None, [], {}


def render_calendar(days: List[Dict[str, Any]], settings: Dict[str, Any]):
    """Render the calendar grid."""
    # Create a lookup dict for days by date
    days_dict = {day['date']: day for day in days}
    
    # Get calendar grid
    grid = calc.month_grid(st.session_state.current_year, st.session_state.current_month)
    
    # Calendar header
    col1, col2, col3 = st.columns([1, 3, 1])
    
    with col1:
        if st.button("◀", key="prev_month"):
            if st.session_state.current_month == 1:
                st.session_state.current_month = 12
                st.session_state.current_year -= 1
            else:
                st.session_state.current_month -= 1
            st.rerun()
    
    with col2:
        month_name = calc.get_month_name(st.session_state.current_month)
        st.markdown(f"<h2 style='text-align: center'>{month_name} {st.session_state.current_year}</h2>", 
                   unsafe_allow_html=True)
    
    with col3:
        if st.button("▶", key="next_month"):
            if st.session_state.current_month == 12:
                st.session_state.current_month = 1
                st.session_state.current_year += 1
            else:
                st.session_state.current_month += 1
            st.rerun()
    
    # Weekday headers
    weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    cols = st.columns(7)
    for i, weekday in enumerate(weekdays):
        with cols[i]:
            st.markdown(f"<div style='text-align: center; font-weight: bold; padding: 10px;'>{weekday}</div>", 
                       unsafe_allow_html=True)
    
    # Calendar grid
    for week in grid:
        cols = st.columns(7)
        for i, day_date in enumerate(week):
            with cols[i]:
                if day_date is None:
                    # Empty cell
                    st.markdown("<div style='height: 80px;'></div>", unsafe_allow_html=True)
                else:
                    render_day_cell(day_date, days_dict.get(day_date), settings)


def render_day_cell(day_date: date, day_data: Dict[str, Any], settings: Dict[str, Any]):
    """Render a single day cell with new design."""
    is_weekend = calc.is_weekend(day_date)
    day_num = day_date.day
    
    if is_weekend:
        # Weekend cell - greyed out with just day number
        st.markdown(f"""
        <div class="weekend-cell">
            <div class="day-number">{day_num}</div>
        </div>
        """, unsafe_allow_html=True)
        return
    
    # Weekday cell
    if day_data:
        status = day_data.get('status', 'NONE')
        is_holiday = day_data.get('is_holiday', False)
        holiday_name = day_data.get('holiday_name', '')
        
        # Get status class and emoji
        status_class = status_to_class(status)
        status_emoji = calc.get_status_emoji(status)
        
        # Holiday badge
        holiday_badge = ""
        if is_holiday:
            holiday_display = holiday_name[:10] if holiday_name else 'Holiday'
            holiday_badge = f'<div class="holiday-badge">🎉 {holiday_display}</div>'
        
        # Render cell container with status class
        st.markdown(f"""
        <div class="day-cell {status_class}">
            <div class="day-number">{day_num}</div>
            <div class="status-emoji">{status_emoji}</div>
            {holiday_badge}
        </div>
        """, unsafe_allow_html=True)
        
        # Status selector inside the cell
        status_options = ['NONE', 'WFH', 'IN_OFFICE', 'VACATION', 'BIOHUB', 'TRAINING', 'OTHER_HOLIDAY']
        status_labels = {
            'NONE': '—',
            'WFH': 'WFH',
            'IN_OFFICE': 'Office',
            'VACATION': 'Vacation',
            'BIOHUB': 'Biohub',
            'TRAINING': 'Training',
            'OTHER_HOLIDAY': 'Other Hol'
        }
        
        current_index = status_options.index(status) if status in status_options else 0
        
        new_status = st.selectbox(
            "",
            options=status_options,
            format_func=lambda x: status_labels.get(x, x),
            index=current_index,
            key=f"status_{day_date.isoformat()}",
            label_visibility="collapsed"
        )
        
        # Update status if changed
        if new_status != status:
            db.upsert_day(st.session_state.user_id, day_date, {'status': new_status})
            st.rerun()
    
    else:
        # No data - empty cell
        status_class = status_to_class('NONE')
        st.markdown(f"""
        <div class="day-cell {status_class}">
            <div class="day-number">{day_num}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Still provide a selector for empty cells
        status_options = ['NONE', 'WFH', 'IN_OFFICE', 'VACATION', 'BIOHUB', 'TRAINING', 'OTHER_HOLIDAY']
        status_labels = {
            'NONE': '—',
            'WFH': 'WFH',
            'IN_OFFICE': 'Office',
            'VACATION': 'Vacation',
            'BIOHUB': 'Biohub',
            'TRAINING': 'Training',
            'OTHER_HOLIDAY': 'Other Hol'
        }
        
        new_status = st.selectbox(
            "",
            options=status_options,
            format_func=lambda x: status_labels.get(x, x),
            index=0,  # Default to NONE
            key=f"status_{day_date.isoformat()}",
            label_visibility="collapsed"
        )
        
        # Create day record if status changed from NONE
        if new_status != 'NONE':
            db.upsert_day(st.session_state.user_id, day_date, {'status': new_status})
            st.rerun()


def render_sidebar(settings: Dict[str, Any], summary: Dict[str, Any]):
    """Render the sidebar with summary and controls."""
    st.sidebar.header("📊 Summary")
    
    # 1. Required Days (big number)
    required_days = summary.get('required_days', 0)
    st.sidebar.metric("Required Days", required_days)
    
    # 2. Balance (with green/red styling)
    balance = summary.get('balance', 0)
    balance_delta = f"{balance:+d}" if balance != 0 else "0"
    balance_delta_color = "normal" if balance == 0 else ("inverse" if balance > 0 else "off")
    st.sidebar.metric("Balance", balance, delta=balance_delta, delta_color=balance_delta_color)
    
    # 3. Completed/Denominator (small lines)
    numerator = summary.get('numerator', 0)
    denominator = summary.get('denominator', 0)
    st.sidebar.markdown(f"**Completed:** {numerator} / {denominator}")
    
    # 4. Progress bar
    required_percent = settings.get('required_percent', 0.60) * 100
    achieved_percent = summary.get('percent_achieved', 0)
    progress_value = min(achieved_percent / required_percent, 1.0) if required_percent > 0 else 0
    st.sidebar.progress(progress_value)
    st.sidebar.markdown(f"**Achievement:** {achieved_percent:.1f}% of {required_percent:.0f}% required")
    
    # Show breakdown of credits
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Credit Breakdown:**")
    status_counts = summary.get('status_counts', {})
    for status in ['IN_OFFICE', 'BIOHUB', 'TRAINING', 'VACATION', 'OTHER_HOLIDAY']:
        count = status_counts.get(status, 0)
        if count > 0:
            st.sidebar.markdown(f"• {status.replace('_', ' ').title()}: {count}")
    
    credited_holidays = summary.get('credited_holidays', 0)
    if credited_holidays > 0:
        st.sidebar.markdown(f"• Credited Holidays: {credited_holidays}")
    
    # Configuration section
    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Configuration")
    
    # Required percentage
    new_required_percent = st.sidebar.slider(
        "Required %",
        min_value=0.0,
        max_value=1.0,
        value=settings.get('required_percent', 0.60),
        step=0.05,
        format="%.0f%%"
    )
    
    # Rounding mode
    new_rounding_mode = st.sidebar.selectbox(
        "Rounding",
        options=['ceil', 'floor', 'round_half_up'],
        index=['ceil', 'floor', 'round_half_up'].index(settings.get('rounding_mode', 'ceil'))
    )
    
    # Holiday treatment for Mon/Fri
    new_monfri_treatment = st.sidebar.selectbox(
        "Mon/Fri Holidays",
        options=['neutral', 'exclude', 'credit'],
        index=['neutral', 'exclude', 'credit'].index(settings.get('monfri_holiday_treatment', 'neutral'))
    )
    
    # Credit weekdays
    credit_options = ['MON', 'TUE', 'WED', 'THU', 'FRI']
    current_credit_weekdays = settings.get('credit_weekdays', ['TUE', 'WED', 'THU'])
    new_credit_weekdays = st.sidebar.multiselect(
        "Credit Weekdays",
        options=credit_options,
        default=current_credit_weekdays
    )
    
    # Update settings if changed
    settings_changed = (
        new_required_percent != settings.get('required_percent', 0.60) or
        new_rounding_mode != settings.get('rounding_mode', 'ceil') or
        new_monfri_treatment != settings.get('monfri_holiday_treatment', 'neutral') or
        set(new_credit_weekdays) != set(current_credit_weekdays)
    )
    
    if settings_changed:
        db.upsert_settings(st.session_state.user_id, {
            'required_percent': new_required_percent,
            'rounding_mode': new_rounding_mode,
            'monfri_holiday_treatment': new_monfri_treatment,
            'credit_weekdays': new_credit_weekdays
        })
        st.rerun()
    
    # Vacation range helper
    st.sidebar.markdown("---")
    st.sidebar.header("🏖️ Vacation Helper")
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=date.today())
    with col2:
        end_date = st.date_input("End Date", value=date.today())
    
    if st.sidebar.button("Set Vacation Range"):
        if calc.validate_date_range(start_date, end_date):
            db.bulk_set_vacation(st.session_state.user_id, start_date, end_date)
            st.sidebar.success(f"Set vacation from {start_date} to {end_date}")
            st.rerun()
        else:
            st.sidebar.error("Invalid date range")
    
    # Export/Import section
    st.sidebar.markdown("---")
    st.sidebar.header("📁 Export/Import")
    
    return settings


def render_export_import(days: List[Dict[str, Any]], settings: Dict[str, Any], summary: Dict[str, Any]):
    """Render export/import controls."""
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        if st.button("Export JSON"):
            json_data = calc.serialize_month(days, settings, summary)
            st.download_button(
                label="Download",
                data=json_data,
                file_name=f"office_tracker_{st.session_state.current_year}_{st.session_state.current_month:02d}.json",
                mime="application/json"
            )
    
    with col2:
        uploaded_file = st.file_uploader("Import JSON", type=['json'])
        if uploaded_file is not None:
            try:
                json_data = uploaded_file.read().decode('utf-8')
                imported_data = calc.deserialize_month(json_data)
                
                if st.button("Confirm Import"):
                    # Import the data (overwrite current month)
                    for day_data in imported_data['days']:
                        db.upsert_day(
                            st.session_state.user_id,
                            day_data['date'],
                            {
                                'status': day_data['status'],
                                'is_holiday': day_data['is_holiday'],
                                'holiday_name': day_data.get('holiday_name', ''),
                                'notes': day_data.get('notes', '')
                            }
                        )
                    st.success("Data imported successfully!")
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Error importing data: {e}")


def status_to_class(status: str) -> str:
    """Map status to CSS class name."""
    status_map = {
        'NONE': 'empty',
        'WFH': 'status-wfh',
        'IN_OFFICE': 'status-in_office',
        'VACATION': 'status-vacation',
        'BIOHUB': 'status-biohub',
        'TRAINING': 'status-training',
        'OTHER_HOLIDAY': 'status-other_holiday'
    }
    return status_map.get(status, 'empty')


def main():
    """Main application function."""
    # Inject CSS styles
    st.markdown("""
    <style>
    .day-cell {
        border: 1px solid #eee;
        border-radius: 0.5rem;
        padding: 1.25rem 0.5rem 0.5rem;
        min-height: 110px;
        position: relative;
        text-align: center;
    }
    
    .day-number {
        position: absolute;
        top: 0.35rem;
        left: 0.5rem;
        font-weight: 600;
        opacity: 0.85;
        font-size: 14px;
    }
    
    .empty {
        background: #fafafa;
        opacity: 0.5;
    }
    
    .status-wfh {
        background: #f3f4f6;
    }
    
    .status-in_office, .status-biohub, .status-training, .status-other_holiday {
        background: #e6f4ea;
    }
    
    .status-vacation {
        background: #fff7cc;
    }
    
    .weekend-cell {
        background-color: #fafafa;
        opacity: 0.5;
        border: 1px solid #eee;
        border-radius: 0.5rem;
        padding: 1.25rem 0.5rem 0.5rem;
        min-height: 110px;
        position: relative;
        text-align: center;
    }
    
    .status-emoji {
        font-size: 18px;
        margin: 10px 0 5px 0;
    }
    
    .holiday-badge {
        font-size: 9px;
        color: red;
        background-color: rgba(255, 255, 255, 0.9);
        padding: 2px 4px;
        border-radius: 3px;
        position: absolute;
        bottom: 5px;
        left: 5px;
        right: 5px;
        font-weight: 500;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.title("🏢 Desk-O-Meter")
    
    # Load data
    settings, days, summary = load_month_data()
    
    if settings is None:
        st.error("Failed to load application data. Please check your Supabase configuration.")
        st.stop()
    
    # Render sidebar
    updated_settings = render_sidebar(settings, summary)
    
    # Render export/import
    render_export_import(days, updated_settings, summary)
    
    # Main calendar view
    render_calendar(days, updated_settings)
    
    # Footer with instructions
    st.markdown("---")
    st.markdown("""
    **Instructions:**
    - Use dropdown in each weekday cell to select status: —, WFH, Office, Vacation, Biohub, Training, Other Hol
    - Holidays are automatically detected and marked with 🎉
    - **New Logic**: VACATION, BIOHUB, TRAINING, and OTHER_HOLIDAY now count as office attendance
    - Denominator = total workdays (no vacation subtraction)
    - Use the sidebar to adjust settings and view detailed progress breakdown
    - Export/import JSON data for backup or sharing
    """)


if __name__ == "__main__":
    main()
