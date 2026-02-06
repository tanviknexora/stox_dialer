import streamlit as st
import pandas as pd
import numpy as np
from datetime import timedelta
import re

st.set_page_config(page_title="CRE Summary Dashboard", layout="wide")
st.title("Single‑file CRE Dialer Dashboard")

# -----------------------------
# Helpers (simplified from your script)
# -----------------------------
def duration_to_timedelta(duration):
    try:
        h, m, s = map(int, str(duration).split(":"))
        return timedelta(hours=h, minutes=m, seconds=s)
    except Exception:
        return timedelta(0)

def normalize_talk_time(val):
    s = str(val)
    if re.match(r"^\d+$", s):
        sec = int(s)
        return f"{sec//3600:02}:{(sec%3600)//60:02}:{sec%60:02}"
    if re.match(r"^\d+:\d+:\d+$", s):
        h, m, s2 = map(int, s.split(":"))
        return f"{h:02}:{m:02}:{s2:02}"
    return "00:00:00"

def simple_cre_pivot(dialers_df: pd.DataFrame) -> pd.DataFrame:
    # Convert times and build hour buckets
    dialers_df = dialers_df.copy()
    dialers_df["Call Start Time"] = pd.to_datetime(dialers_df["Call Start Time"])
    dialers_df["Talk Time"] = pd.to_timedelta(dialers_df["Talk Time"])
    dialers_df["hour"] = dialers_df["Call Start Time"].dt.hour

    def get_interval(hour):
        return f"{hour:02}:00–{hour+1:02}:00"

    dialers_df["Interval"] = dialers_df["hour"].apply(get_interval)

    calls = pd.pivot_table(
        dialers_df,
        index=["CRM ID", "Full Name", "Pool", "TL"],
        columns="Interval",
        values="Date",
        aggfunc="count",
        fill_value=0,
    )

    talks = pd.pivot_table(
        dialers_df,
        index=["CRM ID", "Full Name", "Pool", "TL"],
        columns="Interval",
        values="Talk Time",
        aggfunc="sum",
        fill_value=timedelta(0),
    )
    talks = talks.applymap(lambda x: str(x).split(" ")[-1])

    calls.columns = [f"{c} Calls" for c in calls.columns]
    talks.columns = [f"{c} Talk Time" for c in talks.columns]

    final_df_cre = pd.concat([calls, talks], axis=1).reset_index()
    return final_df_cre

# -----------------------------
# File upload
# -----------------------------
st.subheader("Upload files")

stringee_file = st.file_uploader("Upload Stringee Excel", type=["xlsx", "xls"])
team_file = st.file_uploader("Upload Team List CSV", type=["csv"])

if stringee_file is not None and team_file is not None:
    try:
        # --- Read files ---
        stringee = pd.read_excel(stringee_file)
        team = pd.read_csv(team_file)

        # --- Basic cleaning (very simplified) ---
        stringee["Answer duration"] = stringee["Answer duration"].fillna("00:00:00")
        stringee["Queue duration"] = stringee["Queue duration"].fillna("00:00:00")

        stringee["Queue Duration (timedelta)"] = stringee["Queue duration"].apply(duration_to_timedelta)
        stringee["Answer Duration (timedelta)"] = stringee["Answer duration"].apply(duration_to_timedelta)
        stringee["Total Duration (timedelta)"] = (
            stringee["Queue Duration (timedelta)"] + stringee["Answer Duration (timedelta)"]
        )
        stringee["Total Duration"] = stringee["Total Duration (timedelta)"].apply(
            lambda x: str(x).split(", ")[-1]
        )

        new_string = stringee[
            [
                "Start time",
                "Account",
                "Call status",
                "Answer duration",
                "Hold duration",
                "Total Duration",
                "Customer number",
            ]
        ].copy()

        # Fix datetime
        new_string["Start time"] = pd.to_datetime(
            new_string["Start time"], errors="coerce"
        )
        new_string["Date"] = new_string["Start time"].dt.date
        new_string["Call Start Time"] = new_string["Start time"].dt.strftime("%H:%M:%S")

        # Rename
        new_string.rename(
            columns={
                "Account": "Dialer Name",
                "Customer number": "Number",
                "Call status": "Call Status",
                "Answer duration": "Talk Time",
                "Hold duration": "Hold Time",
                "Total Duration": "Total Call Duration",
            },
            inplace=True,
        )

        df = new_string[
            [
                "Date",
                "Dialer Name",
                "Number",
                "Call Status",
                "Call Start Time",
                "Total Call Duration",
                "Talk Time",
                "Hold Time",
            ]
        ].copy()

        # Normalizations
        df["Talk Time"] = df["Talk Time"].apply(normalize_talk_time)
        df["Total Call Duration"] = df["Total Call Duration"].apply(normalize_talk_time)

        df["Dialer Name"] = (
            df["Dialer Name"]
            .astype(str)
            .str.replace(r"\s+\([^)]*\)|@.*|;.*", "", regex=True)
            .str.strip()
            .str.lower()
        )

        df["Call Status"] = np.where(
            df["Call Status"].str.lower() == "answered",
            "connected",
            "not connected",
        )

        # --- Team merge (expects Dialer Name / Email / Full Name / Pool / TL) ---
        team = team[~team["Email"].str.contains("inactive", case=False, na=False)]
        team["Dialer Name"] = (
            team["Dialer Name"].astype(str).str.strip().str.lower()
        )
        team = team.rename(columns={"Email": "CRM ID"})

        dialers_df = df.merge(team, on="Dialer Name", how="left")

        # --- Build simple CRE pivot ---
        final_df_cre = simple_cre_pivot(dialers_df)

        # --- Show only CRE summary on dashboard ---
        st.subheader("CRE Summary")
        st.dataframe(final_df_cre, use_container_width=True)

    except Exception as e:
        st.error(f"Error while processing file: {e}")
else:
    st.info("Upload both the Stringee Excel and Team CSV to see the results.")
