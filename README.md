# Office Tracker

A clean, minimal Streamlit web app for tracking in-person work with configurable requirements. Built with Python 3.11 and Supabase for data persistence.

## Features

- **Monthly Calendar View**: Interactive calendar showing weekdays with status tracking
- **Work Modes**: Track office, offsite work, WFH, vacation, sick, volunteer, training, and company holidays
- **Holiday Detection**: Automatically credit detected company holidays
- **Flexible Requirements**: Configurable percentage requirements with multiple rounding modes
- **Progress Tracking**: Real-time formula breakdown, progress bar, and balance calculation
- **Self-Service Accounts**: Friends can register with their own email and password
- **Vacation Helper**: Bulk set vacation ranges across dates
- **Export/Import**: JSON export/import for data backup and sharing
- **Month Navigation**: Easy navigation between months with ◀ ▶ arrows

## Setup Instructions

### 1. Create Supabase Project

1. Go to [supabase.com](https://supabase.com) and create a new project
2. Wait for the project to be fully initialized
3. Go to Settings → API to get your project URL and anon/public key
4. In Authentication → Providers → Email, allow new users to sign up
5. Keep email confirmation enabled if users should verify their addresses

### 2. Configure Streamlit Secrets

Create a `.streamlit/secrets.toml` file in your project directory:

```toml
SUPABASE_URL = "https://your-project-ref.supabase.co"
SUPABASE_ANON_KEY = "your-anon-public-key-here"
# Optional. If omitted, Supabase uses the project's configured Site URL.
AUTH_REDIRECT_URL = "https://your-streamlit-app.streamlit.app"
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
  user_id text not null unique,
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
  user_id text not null,
  date date not null,
  status text not null default 'NONE',
  is_holiday boolean not null default false,
  holiday_name text,
  adhoc_credit boolean not null default false,
  notes text,
  unique(date, user_id)
);

-- Every authenticated user can access only their own rows.
alter table settings enable row level security;
alter table days enable row level security;

create policy "Users manage their own settings"
  on settings
  for all
  using (auth.uid()::text = user_id)
  with check (auth.uid()::text = user_id);

create policy "Users manage their own days"
  on days
  for all
  using (auth.uid()::text = user_id)
  with check (auth.uid()::text = user_id);
```

If the tables already exist, enable RLS and verify equivalent policies are present instead of recreating the tables.

### 4. Configure Authentication URLs

In Supabase Authentication → URL Configuration:

1. Set **Site URL** to the deployed Streamlit app URL
2. Add the same URL under **Redirect URLs**
3. For local development, also allow `http://localhost:8501`

New users can then open the app, choose **Create account**, and register without an administrator creating the account.

### 5. Install Dependencies

```bash
pip install -r requirements.txt
```

### 6. Run the Application

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`.

## Configuration Options

### Requirements
- **Required %**: Percentage of eligible days that must be in office (default: 60%)
- **Rounding**: How to round required days calculation (ceil/floor/round_half_up)

### Regions
- **Country**: Holiday calendar country used for automatic company-holiday detection (default: UnitedStates)
- **State**: Optional state for state-specific company holidays
- **Timezone**: Timezone for date calculations

## Business Logic

### Calculation Rules

1. **In-Person Work Days** = Onsite days (`IN_OFFICE`) + offsite work days (`OFFSITE_WORK`, `BIOHUB`, `TRAINING`)
2. **Paid Time Off Days** = Vacation + sick + volunteer days
3. **Company Holidays** = Automatically detected weekday holidays + manually selected company holidays
4. **Weekdays in Month** = All Monday-Friday dates in the calendar month
5. **In-Person Work %** = (In-Person Work Days + Paid Time Off Days + Company Holidays) / Weekdays in Month
6. **Required Days** = rounding(required% × Weekdays in Month)
7. **Balance** = Credited Days - Required Days (positive = banked days, negative = owed days)

Each calendar date contributes at most one credited day. For example, vacation taken on a detected company holiday is not double-counted. Weekend in-person/offsite work retains the app's existing extra-credit behavior, but weekends never increase the denominator.

## File Structure

```
office-tracker/
├── app.py                # Main Streamlit UI and authentication forms
├── auth_helpers.py       # Signup validation and request helpers
├── db.py                 # Supabase database helpers
├── calc.py               # Calendar utilities and business logic
├── test_auth_helpers.py  # Signup helper tests
├── test_app_auth_ui.py   # Authentication UI smoke tests
├── test_calc.py          # Calculation tests
├── requirements.txt      # Python dependencies
├── README.md             # This file
└── .streamlit/
    └── secrets.toml      # Supabase credentials (not in git)
```

## Deployment

### Streamlit Cloud

1. Push your code to GitHub (excluding `.streamlit/secrets.toml`)
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repository
4. Add your secrets in the Streamlit Cloud dashboard under "Secrets"
5. Set `AUTH_REDIRECT_URL` and the Supabase Site URL to the deployed app URL
6. Deploy!

### Local Development

The app runs locally with the setup instructions above. Make sure your Supabase project allows connections from your IP address.

## Future Enhancements

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
2. **Connection errors**: Check your `SUPABASE_URL` and `SUPABASE_ANON_KEY` in secrets
3. **Signup is disabled**: Enable email signups under Supabase Authentication → Providers
4. **Confirmation link redirects incorrectly**: Check the Supabase Site URL, Redirect URLs, and `AUTH_REDIRECT_URL`
5. **New users cannot load data**: Verify RLS is enabled and both tables have policies matching `auth.uid()::text = user_id`
6. **Holiday detection issues**: Verify your `DEFAULT_COUNTRY` and `DEFAULT_STATE` settings
7. **Import/export errors**: Ensure JSON files follow the expected schema format

### Database Reset

To reset your data:

```sql
DELETE FROM days WHERE user_id = '<supabase-user-id>';
DELETE FROM settings WHERE user_id = '<supabase-user-id>';
```

The app will recreate default settings and re-seed the current month on next load.

## License

MIT License - feel free to modify and distribute as needed.
