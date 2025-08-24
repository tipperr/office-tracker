# Office Tracker

A clean, minimal Streamlit web app for tracking office attendance with configurable requirements and holiday handling. Built with Python 3.11 and Supabase for data persistence.

## Features

- **Monthly Calendar View**: Interactive calendar showing weekdays with status tracking
- **Status Cycling**: Click cells to cycle through None → Office → WFH → Vacation
- **Holiday Detection**: Automatic holiday detection with configurable credit rules
- **Flexible Requirements**: Configurable percentage requirements with multiple rounding modes
- **Progress Tracking**: Real-time progress bar and balance calculation
- **Vacation Helper**: Bulk set vacation ranges across dates
- **Export/Import**: JSON export/import for data backup and sharing
- **Month Navigation**: Easy navigation between months with ◀ ▶ arrows

## Setup Instructions

### 1. Create Supabase Project

1. Go to [supabase.com](https://supabase.com) and create a new project
2. Wait for the project to be fully initialized
3. Go to Settings → API to get your project URL and service role key

### 2. Configure Streamlit Secrets

Create a `.streamlit/secrets.toml` file in your project directory:

```toml
SUPABASE_URL = "https://your-project-ref.supabase.co"
SUPABASE_SERVICE_KEY = "your-service-role-key-here"
TIMEZONE = "America/Los_Angeles"
DEFAULT_COUNTRY = "UnitedStates"
DEFAULT_STATE = ""
```

**Important**: Never commit your `secrets.toml` file to version control. Add `.streamlit/` to your `.gitignore`.

### 3. Create Database Tables

Run this SQL in your Supabase SQL Editor (or the app will prompt you if tables don't exist):

```sql
-- Settings table for user preferences
create table if not exists settings (
  id serial primary key,
  user_id text not null default 'rachel',
  required_percent numeric not null default 0.60,
  rounding_mode text not null default 'ceil',
  credit_weekdays_json jsonb not null default '["TUE","WED","THU"]',
  monfri_holiday_treatment text not null default 'neutral',
  country text not null default 'UnitedStates',
  state text,
  timezone text not null default 'America/Los_Angeles'
);

-- Days table for tracking daily status
create table if not exists days (
  id bigserial primary key,
  user_id text not null default 'rachel',
  date date not null,
  status text not null default 'NONE',
  is_holiday boolean not null default false,
  holiday_name text,
  adhoc_credit boolean not null default false,
  notes text,
  unique(date, user_id)
);

-- For v1, keep RLS off or use service key
-- Later for auth, enable RLS and add policies on user_id
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Run the Application

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`.

## Configuration Options

### Requirements
- **Required %**: Percentage of eligible days that must be in office (default: 60%)
- **Rounding**: How to round required days calculation (ceil/floor/round_half_up)

### Holiday Handling
- **Credit Weekdays**: Which weekdays get credited when they're holidays (default: Tue/Wed/Thu)
- **Mon/Fri Holidays**: How to treat Monday/Friday holidays:
  - `neutral`: No effect on calculation
  - `exclude`: Remove from denominator
  - `credit`: Add to numerator

### Regions
- **Country**: Holiday calendar country (default: UnitedStates)
- **State**: Optional state for state-specific holidays
- **Timezone**: Timezone for date calculations

## Business Logic

### Calculation Rules

1. **Workdays** = All Monday-Friday in the month
2. **Denominator** = Workdays - Vacation days - (excluded holidays if Mon/Fri treatment = exclude)
3. **Numerator** = In Office days + Credited holidays
4. **Required Days** = rounding(required% × denominator)
5. **Balance** = Numerator - Required Days (positive = banked days, negative = owed days)

### Holiday Credit Rules

- Holidays on credited weekdays (Tue/Wed/Thu by default) are automatically credited
- Monday/Friday holidays follow the Mon/Fri treatment setting:
  - `neutral`: No effect
  - `exclude`: Removed from denominator (makes requirement easier)
  - `credit`: Added to numerator (counts as office day)

## File Structure

```
office-tracker/
├── app.py              # Main Streamlit UI
├── db.py               # Supabase database helpers
├── calc.py             # Calendar utilities and business logic
├── requirements.txt    # Python dependencies
├── README.md          # This file
└── .streamlit/
    └── secrets.toml   # Supabase credentials (not in git)
```

## Deployment

### Streamlit Cloud

1. Push your code to GitHub (excluding `.streamlit/secrets.toml`)
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repository
4. Add your secrets in the Streamlit Cloud dashboard under "Secrets"
5. Deploy!

### Local Development

The app runs locally with the setup instructions above. Make sure your Supabase project allows connections from your IP address.

## Future Enhancements

### Authentication (TODO)
```python
# TODO(auth): Switch to Supabase Auth, enable RLS, add user_id from auth context
```

To add authentication:
1. Enable Row Level Security (RLS) on both tables
2. Add policies: `users can only access their own rows`
3. Replace service key with anon key + RLS
4. Add Supabase Auth integration to get real user_id

### ESP32/IoT Integration (TODO)
```python
# TODO(device): Expose /api/month?year=YYYY&month=MM via FastAPI for ESP32 clients
```

To add IoT support:
1. Create a FastAPI microservice alongside Streamlit
2. Expose JSON endpoints using `calc.serialize_month()`
3. Or use Supabase PostgREST directly for API access
4. The `serialize_month()` function provides a stable schema for external clients

### API Endpoints (Future)

The app is designed to easily expose JSON APIs:

```
GET /api/month?year=2024&month=12&user_id=rachel
```

Returns the same JSON format as the export feature, suitable for ESP32 e-ink displays or CLI tools.

## Troubleshooting

### Common Issues

1. **"Tables don't exist"**: Run the DDL commands in your Supabase SQL editor
2. **Connection errors**: Check your `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` in secrets
3. **Holiday detection issues**: Verify your `DEFAULT_COUNTRY` and `DEFAULT_STATE` settings
4. **Import/export errors**: Ensure JSON files follow the expected schema format

### Database Reset

To reset your data:

```sql
DELETE FROM days WHERE user_id = 'rachel';
DELETE FROM settings WHERE user_id = 'rachel';
```

The app will recreate default settings and re-seed the current month on next load.

## License

MIT License - feel free to modify and distribute as needed.
