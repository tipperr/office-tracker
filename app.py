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
from supabase import create_client

def build_weeks(year: int, month: int):
    """Return list of weeks; each is a list of 7 datetime.date (Mon..Sun).
    Includes spillover days so weekday alignment is preserved."""
    cal = calendar.Calendar(firstweekday=0)  # 0 = Monday
    return [list(week) for week in cal.monthdatescalendar(year, month)]

def initial_week_index(weeks, today=None) -> int:
    if today is None:
        today = date.today()
    for i, wk in enumerate(weeks):
        if today in wk:
            return i
    return 0

def get_auth_client():
    url = db.get_secret("SUPABASE_URL")
    anon = db.get_secret("SUPABASE_ANON_KEY")
    if not url or not anon:
        st.error("Supabase URL / ANON key missing.")
        st.stop()
    return create_client(url, anon)

def _display_name() -> str:
    if "display_name" in st.session_state and st.session_state["display_name"]:
        return str(st.session_state["display_name"])
    e = st.session_state.get("email") or ""
    return (e.split("@")[0].title() if e else "there")

def render_login():
    st.title("Sign in")
    st.markdown("Track in-office requirements (60% of weekdays), holidays, and weekend credits.")
    with st.expander("What is this?", expanded=False):
        st.markdown(
            "- **Counts:** Tue–Thu holidays and any day you mark as Office/Biohub/Training/Vacation count toward your 60%.\n"
            "- **Weekends:** Don't increase the denominator, but **do** add credit if marked as Office-like.\n"
            "- **Privacy:** With RLS enabled, you only see your own data.\n"
        )
    with st.form("login"):
        email = st.text_input("Email", value="", autocomplete="username")
        password = st.text_input("Password", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Sign in")
    if submitted:
        sb = get_auth_client()
        try:
            res = sb.auth.sign_in_with_password({"email": email, "password": password})
            # Persist identity for this session
            st.session_state["uid"] = res.user.id
            st.session_state["sb_client"] = sb
            # Store display info for greeting
            try:
                user_email = getattr(res.user, "email", None)
                user_name = None
                meta = getattr(res.user, "user_metadata", None) or {}
                if isinstance(meta, dict):
                    user_name = meta.get("full_name") or meta.get("name")
                if user_email and not user_name:
                    user_name = user_email.split("@")[0]
                if user_email:  st.session_state["email"] = user_email
                if user_name:   st.session_state["display_name"] = user_name
            except Exception:
                pass
            st.success("Signed in")
            st.rerun()
        except Exception as e:
            st.error(f"Login failed: {e}")

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
.weekday-label { font-size: 0.85rem; opacity: .75; margin-bottom: .25rem; }
</style>
""", unsafe_allow_html=True)

WEEKDAY_ABBR = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

# Gate the app UI behind login
if "uid" not in st.session_state:
    render_login()
    st.stop()

# Show greeting for authenticated user
st.markdown(f"### Hi, {_display_name()} 👋")
st.caption("You're signed in. Your data is private to your account.")

# Initialize session state
if 'current_year' not in st.session_state:
    today = date.today()
    st.session_state.current_year = today.year
    st.session_state.current_month = today.month

if 'user_id' not in st.session_state:
    st.session_state.user_id = 'rachel'  # Default user for v1

# Compute weeks for the visible month
year = st.session_state.current_year
month = st.session_state.current_month
weeks = build_weeks(year, month)
ym_key = f"{year}-{month:02d}"

# Reset week index when the month changes
if st.session_state.get("ym_key") != ym_key:
    st.session_state["ym_key"] = ym_key
    st.session_state["week_idx"] = initial_week_index(weeks)

# Toggle we can use later to switch views (kept False by default)
st.session_state.setdefault("mobile_week_view", False)


def load_month_data():
    """Load data for the current month."""
    try:
        # Initialize schema if needed
        db.init_schema_if_needed()
        
        # Get settings and days
        settings = db.get_settings()
        days = db.get_month_days(
            None,
            st.session_state.current_year,
            st.session_state.current_month
        )
        
        # Compute summary
        summary = calc.compute_summary(days, settings)
        
        return settings, days, summary
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None, [], {}


def render_week(week_dates, days_by_iso, settings, visible_year, visible_month):
    """Render a single week in 2-row grid: Mon-Thu, then Fri-Sun."""
    # Row 1: Mon..Thu with weekday labels
    cols = st.columns(4, gap="small")
    for i, d in enumerate(week_dates[:4]):
        with cols[i]:
            # Display weekday label
            st.markdown(f'<div class="weekday-label">{WEEKDAY_ABBR[i]}</div>', unsafe_allow_html=True)
            # Look up record by ISO date string
            iso_key = d.isoformat()
            rec = days_by_iso.get(iso_key)
            render_day_cell(d, rec, settings)

    # Row 2: Fri..Sun with weekday labels
    cols = st.columns(3, gap="small")
    for i, d in enumerate(week_dates[4:]):
        with cols[i]:
            # Display weekday label (Fri=4, Sat=5, Sun=6)
            st.markdown(f'<div class="weekday-label">{WEEKDAY_ABBR[i + 4]}</div>', unsafe_allow_html=True)
            # Look up record by ISO date string
            iso_key = d.isoformat()
            rec = days_by_iso.get(iso_key)
            render_day_cell(d, rec, settings)


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
        # Weekend cell - interactive but slightly muted
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
            
            # Render weekend cell with status class and slight opacity
            st.markdown(f"""
            <div class="weekend-cell {status_class}">
                <div class="day-number">{day_num}</div>
                <div class="weekend-label">Weekend</div>
                <div class="status-emoji">{status_emoji}</div>
                {holiday_badge}
            </div>
            """, unsafe_allow_html=True)
            
            # Status selector for weekends
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
                db.upsert_day(None, day_date, {'status': new_status})
                st.rerun()
        
        else:
            # No data - empty weekend cell
            status_class = status_to_class('NONE')
            st.markdown(f"""
            <div class="weekend-cell {status_class}">
                <div class="day-number">{day_num}</div>
                <div class="weekend-label">Weekend</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Still provide a selector for empty weekend cells
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
                db.upsert_day(None, day_date, {'status': new_status})
                st.rerun()
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
            db.upsert_day(None, day_date, {'status': new_status})
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
            db.upsert_day(None, day_date, {'status': new_status})
            st.rerun()


def render_sidebar(settings: Dict[str, Any], summary: Dict[str, Any]):
    """Render the sidebar with summary and controls."""
    # Sign out button
    with st.sidebar:
        if st.button("Sign out"):
            try:
                get_auth_client().auth.sign_out()
            except Exception:
                pass
            st.session_state.pop("sb_client", None)
            st.session_state.clear()
            st.rerun()
    
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
    
    # Weekend behavior helper text
    st.sidebar.caption("💡 Weekends don't increase the denominator; marking an office status on a weekend does add credit.")
    
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
        db.upsert_settings(db.get_current_user_id(), {
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
            db.bulk_set_vacation(None, start_date, end_date)
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
                            None,
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
    
    .weekend-label {
        font-size: 10px;
        color: #666;
        margin-top: 15px;
        font-weight: 500;
        opacity: 0.7;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.title("🏢 Desk-O-Meter")
    
    # Load data
    settings, days, summary = load_month_data()
    
    if settings is None:
        st.error("Failed to load application data. Please check your Supabase configuration.")
        st.stop()
    
    # Map "YYYY-MM-DD" -> row (avoid date-object mismatches)
    days_by_iso = {}
    for r in days:
        # Handle PostgREST returning str or date
        raw = r.get("date")
        iso = None
        if raw is None:
            continue
        if isinstance(raw, str):
            # normalize "YYYY-MM-DD..." to first 10 chars
            iso = raw[:10]
        else:
            # datetime.date/datetime
            try:
                iso = raw.isoformat()[:10]
            except Exception:
                continue
        days_by_iso[iso] = r

    # Sidebar toggle to switch on week view
    with st.sidebar:
        st.checkbox("📱 Week view (mobile)", key="mobile_week_view",
                    help="Shows one week at a time with correct weekday alignment.")
    
    # Render sidebar
    updated_settings = render_sidebar(settings, summary)
    
    # Render export/import
    render_export_import(days, updated_settings, summary)
    
    # Main calendar view - branch between week and month view
    if st.session_state.get("mobile_week_view", False):
        total_weeks = len(weeks)
        wk = int(st.session_state.get("week_idx", 0))
        wk = max(0, min(wk, total_weeks - 1))

        nav_l, nav_c, nav_r = st.columns([1, 3, 1])
        with nav_l:
            if st.button("◀ Prev week", use_container_width=True, key=f"wk-prev-{ym_key}-{wk}"):
                st.session_state["week_idx"] = max(0, wk - 1)
                st.rerun()
        with nav_c:
            st.markdown(f"#### Week {wk + 1} of {total_weeks}")
        with nav_r:
            if st.button("Next week ▶", use_container_width=True, key=f"wk-next-{ym_key}-{wk}"):
                st.session_state["week_idx"] = min(total_weeks - 1, wk + 1)
                st.rerun()

        render_week(weeks[wk], days_by_iso, updated_settings, year, month)
    else:
        # Existing month view call stays as-is:
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
