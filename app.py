import streamlit as st
import pandas as pd
import numpy as np
from datetime import timedelta
import re

st.set_page_config(page_title="CRE Summary Dashboard", layout="wide")
st.title("CRE Dialer Dashboard - Fixed")

# -----------------------------
# Helper functions (EXACTLY from your original script)
# -----------------------------
def duration_to_timedelta(duration):
    try:
        hours, minutes, seconds = map(int, str(duration).split(':'))
        return timedelta(hours=hours, minutes=minutes, seconds=seconds)
    except:
        return timedelta(0)

def fix_string_datetime(date_str):
    try:
        parsed_date = pd.to_datetime(date_str, errors='coerce', format='%Y-%m-%d %H:%M:%S.%f')
        return parsed_date
    except:
        return pd.NaT

def split_date_time(df, col_name):
    df[col_name] = pd.to_datetime(df[col_name], errors='coerce', format='%Y/%m/%d %H:%M:%S')
    df['Date'] = df[col_name].dt.date
    df['Call Start Time'] = df[col_name].dt.strftime('%H:%M:%S')
    return df

def normalize_talk_time(talk_time):
    s = str(talk_time)
    if re.match(r"^\d+$", s):
        seconds = int(s)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return f"{hours:02}:{minutes:02}:{seconds:02}"
    elif re.match(r"^\d+:\d+:\d+$", s):
        parts = s.split(":")
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])
        return f"{hours:02}:{minutes:02}:{seconds:02}"
    return talk_time

def get_interval(hour):
    if hour < 8: return '0 to 8 AM'
    elif hour < 9: return '8 to 9 AM'
    elif hour < 10: return '9 to 10 AM'
    elif hour < 11: return '10 to 11 AM'
    elif hour < 12: return '11 to 12 PM'
    elif hour < 13: return '12 to 13 PM'
    elif hour < 14: return '13 to 14 PM'
    elif hour < 15: return '14 to 15 PM'
    elif hour < 16: return '15 to 16 PM'
    elif hour < 17: return '16 to 17 PM'
    elif hour < 18: return '17 to 18 PM'
    else: return '18+'

def build_cre_pivot(dialers_df):
    dialers_df['Call Start Time'] = pd.to_datetime(dialers_df['Call Start Time'])
    dialers_df['Talk Time'] = pd.to_timedelta(dialers_df['Talk Time'])
    dialers_df['hour'] = dialers_df['Call Start Time'].dt.hour
    dialers_df['Interval'] = dialers_df['hour'].apply(get_interval)

    call_counts = pd.pivot_table(
        dialers_df,
        index=['CRM ID', 'Full Name', 'Pool', 'TL'],
        columns='Interval',
        values='Date',
        aggfunc='count',
        fill_value=0
    )

    talk_times = pd.pivot_table(
        dialers_df,
        index=['CRM ID', 'Full Name', 'Pool', 'TL'],
        columns='Interval',
        values='Talk Time',
        aggfunc='sum',
        fill_value=pd.Timedelta(0)
    )
    talk_times = talk_times.applymap(lambda x: str(x).split(' ')[-1])

    call_counts.columns = [f'{col} - Calls' for col in call_counts.columns]
    talk_times.columns = [f'{col} - Talk Time' for col in talk_times.columns]
    
    final_df_cre = pd.concat([call_counts, talk_times], axis=1).reset_index()
    return final_df_cre

# -----------------------------
# File upload
# -----------------------------
st.subheader("Upload files")

stringee_file = st.file_uploader("Upload Stringee Excel", type=["xlsx", "xls"])
team_file = st.file_uploader("Upload Team List CSV", type=["csv"])

if stringee_file is not None and team_file is not None:
    try:
        with st.spinner("Processing files..."):
            # --- EXACTLY like your original script ---
            stringee = pd.read_excel(stringee_file)
            stringee['Answer duration'] = stringee['Answer duration'].fillna('00:00:00')
            stringee['Queue duration'] = stringee['Queue duration'].fillna('00:00:00')

            stringee['Queue Duration (timedelta)'] = stringee['Queue duration'].apply(duration_to_timedelta)
            stringee['Answer Duration (timedelta)'] = stringee['Answer duration'].apply(duration_to_timedelta)
            stringee['Total Duration (timedelta)'] = (stringee['Queue Duration (timedelta)'] + 
                                                    stringee['Answer Duration (timedelta)'])
            stringee['Total Duration'] = stringee['Total Duration (timedelta)'].apply(lambda x: str(x).split(", ")[-1])
            stringee = stringee.drop(columns=['Queue Duration (timedelta)', 'Answer Duration (timedelta)', 'Total Duration (timedelta)'])

            new_string = stringee[['Start time','Account','Call status','Answer duration','Hold duration','Total Duration','Customer number']].copy()
            
            # CRITICAL: Fix datetime like original
            new_string['Start time'] = new_string['Start time'].apply(fix_string_datetime)
            new_string['Start time'] = new_string['Start time'].dt.strftime('%Y/%m/%d %H:%M:%S')
            new_string = split_date_time(new_string, 'Start time')

            string_copy = new_string.copy()
            string_copy['Source'] = 'Stringee'
            string_copy.rename(columns={
                'Account': 'Dialer Name',
                'Customer number': 'Number',
                'Call status': 'Call Status',
                'Answer duration': 'Talk Time',
                'Hold duration': 'Hold Time',
            }, inplace=True)

            string_selected = string_copy[['Source','Date', 'Dialer Name','Number', 'Call Status','Call Start Time','Total Duration', 'Talk Time', 'Hold Time']]
            combined = string_selected.copy()
            combined_df = combined.copy()
            
            # EXACT regex from original
            combined_df['Dialer Name'] = combined_df['Dialer Name'].str.replace(r"\s*\([^)]*\)|@.*|;.*", "", regex=True)
            combined_df['Dialer Name'] = combined_df['Dialer Name'].fillna(combined['Dialer Name'])
            combined_df['Hold Time'] = combined_df['Hold Time'].fillna('00:00:00')

            A = combined_df.copy()
            A1 = A[A['Dialer Name'].notnull()].copy()
            A1['Talk Time'] = A1['Talk Time'].apply(normalize_talk_time)
            A1['Total Call Duration'] = A1['Total Duration'].apply(normalize_talk_time)
            A1.rename(columns={'Total Duration': 'Total Call Duration'}, inplace=True)
            
            A1['Call Status'] = A1['Call Status'].apply(lambda x: 'connected' if str(x).lower() == 'answered' else 'not connected')
            combined_df_1 = A1[~A1['Dialer Name'].isin([None, '---'])].reset_index(drop=True)

            # Team processing EXACTLY like original
            ref_d = pd.read_csv(team_file)
            ref = ref_d[~ref_d['Email'].str.contains('inactive', case=False, na=False)].copy()
            
            for df in [ref, combined_df_1]:
                df['Dialer Name'] = (
                    df['Dialer Name']
                    .astype(str)
                    .str.replace(r'\s+', ' ', regex=True)
                    .str.strip()
                    .str.replace(r'@.*', '', regex=True)
                    .str.replace(r'\(.*', '', regex=True)
                    .str.strip()
                    .str.lower()
                )
            
            ref = ref.drop_duplicates(subset=['Dialer Name','Email','Dialer'])
            ref.rename(columns={'Email': 'CRM ID'}, inplace=True)

            combined_df_1['Dialer Name'] = combined_df_1['Dialer Name'].astype(str)
            ref['Dialer Name'] = ref['Dialer Name'].astype(str)

            combined_df_2 = combined_df_1.merge(ref, how='left', left_on='Dialer Name', right_on='Dialer Name')
            
            # CRITICAL: Create Dialers exactly like original
            Dialers = combined_df_2[combined_df_2['CRM ID'].notnull() & combined_df_2['Talk Time'].notnull()].copy()
            Dialers = Dialers.drop_duplicates(subset=['Number','Call Start Time'])

            # Date/Time processing for gaps (optional but matches original)
            Dialers['Date'] = pd.to_datetime(Dialers['Date'], format='%Y-%m-%d', errors='coerce')
            Dialers['Call Start Time'] = pd.to_datetime(
                Dialers['Date'].dt.strftime('%Y-%m-%d').fillna('1900-01-01') + ' ' + Dialers['Call Start Time'],
                format='%Y-%m-%d %H:%M:%S', errors='coerce'
            )
            Dialers['Total Call Duration'] = Dialers['Total Call Duration'].apply(
                lambda x: pd.to_timedelta(x) if isinstance(x, str) else pd.Timedelta(0)
            )
            Dialers = Dialers.sort_values(by=['Date', 'CRM ID', 'Call Start Time']).reset_index(drop=True)

            # Build final_df_cre EXACTLY like original
            final_df_cre = build_cre_pivot(Dialers)

        # --- Display results ---
        st.success(f"✅ Processed {len(Dialers)} dialer records from {len(final_df_cre)} CREs")
        st.subheader("CRE Summary")
        st.dataframe(final_df_cre, use_container_width=True)

    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        st.exception(e)
else:
    st.info("👆 Please upload both Stringee Excel and Team CSV files")
