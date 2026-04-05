import streamlit as st
import pandas as pd
from datetime import date, timedelta
from supabase import create_client, Client
from garmin_client import get_garmin_client
import logging

# ── Page Configuration ───────────────────────────────────────────────────────
st.set_page_config(page_title='Fitness Command Center', layout='wide')

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Supabase Initialization ──────────────────────────────────────────────────
@st.cache_resource
def get_supabase_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase_client()

# ── Data Fetching (Supabase) ────────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_today_stats(cdate: str):
    """Fetch today's summary from Supabase."""
    try:
        res = supabase.table("daily_logs").select("*").eq("date", cdate).execute()
        return res.data[0] if res.data else None
    except Exception as exc:
        st.error(f"Error fetching daily log: {exc}")
        return None

# ── Data Fetching (Garmin) ──────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_garmin_calendar(start_date: date, days: int = 7):
    """Fetch Garmin calendar events for the next N days."""
    client = get_garmin_client()
    if not client:
        return []

    events = []
    # Garmin calendar API usually works by month.
    # To cover a rolling 7-day window, we might need two months if we're at month-end.
    check_dates = [start_date + timedelta(days=i) for i in range(days)]
    months_to_fetch = set((d.year, d.month) for d in check_dates)

    all_items = []
    for year, month in months_to_fetch:
        month_idx = month - 1
        path = f"/calendar-service/year/{year}/month/{month_idx}"
        try:
            data = client.connectapi(path, method="GET")
            all_items.extend(data.get("calendarItems", []))
        except Exception as exc:
            logger.error(f"Error fetching Garmin calendar for {year}-{month}: {exc}")

    # Filter to the requested range and relevant types
    start_str = start_date.isoformat()
    end_str = (start_date + timedelta(days=days-1)).isoformat()
    
    for item in all_items:
        idate = item.get("date")
        if idate and start_str <= idate <= end_str:
            events.append({
                "date": idate,
                "title": item.get("title"),
                "type": item.get("itemType"),
            })
    
    return sorted(events, key=lambda x: x["date"])

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🛡️ Command Center")
    today = date.today()
    st.write(f"📅 **Today:** {today.strftime('%A, %b %d')}")
    
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.subheader("⚖️ Weight Check-in")
    with st.form("weight_form", clear_on_submit=True):
        weight = st.number_input("Weight (kg)", min_value=30.0, max_value=200.0, step=0.1, format="%.1f")
        submitted = st.form_submit_button("Log Weight")
        
        if submitted:
            try:
                data = {"date": today.isoformat(), "weight_kg": weight}
                supabase.table("weight_logs").upsert(data).execute()
                st.success(f"Logged {weight} kg!")
            except Exception as exc:
                st.error(f"Failed to log weight: {exc}")

# ── Main Dashboard ───────────────────────────────────────────────────────────
st.title("Fitness Command Center 🚀")

today_str = date.today().isoformat()
stats = fetch_today_stats(today_str)

col1, col2, col3 = st.columns(3)

if stats:
    target = stats.get("target_calories", 0)
    consumed = stats.get("consumed_calories", 0)
    remaining = target - consumed
    
    col1.metric("Target Calories", f"{target:,} kcal")
    col2.metric("Consumed", f"{consumed:,} kcal")
    col3.metric("Remaining", f"{remaining:,} kcal", delta_color="normal")
else:
    st.info("No data for today yet. Run the morning briefing to initialize.")

st.divider()
st.subheader("📅 Training Forecast (Next 7 Days)")
calendar_events = fetch_garmin_calendar(date.today())

if calendar_events:
    df = pd.DataFrame(calendar_events)
    # Prettier display
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%b %d (%a)')
    st.table(df[['date', 'title', 'type']])
else:
    st.write("No upcoming events found on your Garmin calendar.")
