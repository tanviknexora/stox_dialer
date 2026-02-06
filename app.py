import streamlit as st
import pandas as pd
import numpy as np
from datetime import timedelta
import re

st.set_page_config(page_title="CRE Summary Dashboard", layout="wide", initial_sidebar_state="expanded")
st.title("🚀 CRE Dialer Dashboard - Production Ready")

# -----------------------------
# Enhanced Helper Functions
# -----------------------------
@st.cache_data
def duration_to_timedelta(duration):
    try:
        hours, minutes, seconds = map(int, str(duration).split(':'))
        return timedelta(hours=hours, minutes=minutes, seconds=seconds)
    except:
        return timedelta(0)

@st.cache_data
def fix_string_datetime(date_str):
    try:
        parsed_date = pd.to_datetime(date_str, errors='coerce')
        return parsed_date
    except:
        return pd.NaT

def split_date_time(df, col_name):
    df = df.copy()
    df[col_name] = pd.to_datetime(df[col_name], errors='coerce', format='%Y/%m/%d %H:%M:%S')
    df['Date'] = df[col_name].dt.date
    df['Call Start Time'] = df[col_name].dt.strftime('%H:%M:%S')
    return df

@st.cache_data
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
    return "00:00:00"

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

@st.cache_data
def build_cre_pivot(dialers_df):
    df = dialers_df.copy()
    df['Call Start Time'] = pd.to_datetime(df['Call Start Time'])
    df['Talk Time'] = pd.to_timedelta(df['Talk Time'].fillna(pd.Timedelta(0)))
    df['hour'] = df['Call Start Time'].dt.hour
    df['Interval'] = df['hour'].apply(get_interval)

    # Ensure required columns exist
    for col in ['CRM ID', 'Full Name', 'Pool', 'TL']:
        if col not in df.columns:
            df[col] = 'Unknown'

    call_counts = pd.pivot_table(
        df,
        index=['CRM ID', 'Full Name', 'Pool', 'TL'],
        columns='Interval',
        values='Date',
        aggfunc='count',
        fill_value=0
    )

    talk_times = pd.pivot_table(
        df,
        index=['CRM ID', 'Full Name', 'Pool', 'TL'],
        columns='Interval',
        values='Talk Time',
        aggfunc='sum',
        fill_value=pd.Timedelta(0)
    )
    talk_times = talk_times.applymap(lambda x: str(x).split(' ')[-1] if pd.notnull(x) else '00:00:00')

    call_counts.columns = [f'{col} Calls' for col in call_counts.columns]
    talk_times.columns = [f'{col} Talk Time' for col in talk_times.columns]
    
    final_df_cre = pd.concat([call_counts, talk_times], axis=1).reset_index()
    return final_df_cre

# -----------------------------
# Main Processing Pipeline
# -----------------------------
def process_files(stringee_file, team_file):
    """Complete processing pipeline matching original script"""
    
    # Read Stringee file
    stringee = pd.read_excel(stringee_file)
    st.info(f"📊 Loaded {len(stringee)} call records")
    
    stringee['Answer duration'] = stringee['Answer duration'].fillna('00:00:00')
    stringee['Queue duration'] = stringee['Queue duration'].fillna('00:00:00')

    stringee['Queue Duration (timedelta)'] = stringee['Queue duration'].apply(duration_to_timedelta)
    stringee['Answer Duration (timedelta)'] = stringee['Answer duration'].apply(duration_to_timedelta)
    stringee['Total Duration (timedelta)'] = (stringee['Queue Duration (timedelta)'] + 
                                            stringee['Answer Duration (timedelta)'])
    stringee['Total Duration'] = stringee['Total Duration (timedelta)'].apply(lambda x: str(x).split(", ")[-1])
    stringee = stringee.drop(columns=['Queue Duration (timedelta)', 'Answer Duration (timedelta)', 'Total Duration (timedelta)'])

    new_string = stringee[['Start time','Account','Call status','Answer duration','Hold duration','Total Duration','Customer number']].copy()
    
    # Fix datetime processing
    new_string['Start time'] = new_string['Start time'].apply(fix_string_datetime)
    new_string['Start time'] = new_string['Start time'].dt.strftime('%Y/%m/%d %H:%M:%S')
    new_string = split_date_time(new_string, 'Start time')

    # Data cleaning pipeline
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
    combined_df = string_selected.copy()
    
    # Dialer Name cleaning
    combined_df['Dialer Name'] = combined_df['Dialer Name'].str.replace(r"\s*\([^)]*\)|@.*|;.*", "", regex=True)
    combined_df['Dialer Name'] = combined_df['Dialer Name'].fillna(combined_df['Dialer Name'])
    combined_df['Hold Time'] = combined_df['Hold Time'].fillna('00:00:00')

    # Remove null dialer names
    A1 = combined_df[combined_df['Dialer Name'].notnull()].copy()
    A1['Talk Time'] = A1['Talk Time'].apply(normalize_talk_time)
    A1['Total Call Duration'] = A1['Total Duration'].apply(normalize_talk_time)
    A1.rename(columns={'Total Duration': 'Total Call Duration'}, inplace=True)
    
    A1['Call Status'] = A1['Call Status'].apply(lambda x: 'connected' if str(x).lower() == 'answered' else 'not connected')
    combined_df_1 = A1[~A1['Dialer Name'].isin([None, '---'])].reset_index(drop=True)

    # Team file processing
    ref_d = pd.read_csv(team_file)
    st.info(f"👥 Loaded {len(ref_d)} team members")
    
    ref = ref_d[~ref_d['Email'].str.contains('inactive', case=False, na=False)].copy()
    
    # Exact cleaning from original script
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
    
    ref = ref.drop_duplicates(subset=['Dialer Name','Email'])
    ref.rename(columns={'Email': 'CRM ID'}, inplace=True)

    # Merge dialer names
    combined_df_2 = combined_df_1.merge(ref, how='left', left_on='Dialer Name', right_on='Dialer Name')
    
    # Create Dialers (matched CREs only)
    Dialers = combined_df_2[combined_df_2['CRM ID'].notnull() & combined_df_2['Talk Time'].notnull()].copy()
    Dialers = Dialers.drop_duplicates(subset=['Number','Call Start Time'])
    
    # Final pivot
    final_df_cre = build_cre_pivot(Dialers)
    
    return final_df_cre, Dialers, len(ref_d), len(combined_df_2)

# -----------------------------
# File Upload Section
# -----------------------------
col1, col2 = st.columns([3,1])
with col1:
    st.subheader("📁 Upload Files")
    stringee_file = st.file_uploader("Stringee Excel File", type=["xlsx", "xls"], help="Upload your Stringee call data")
with col2:
    team_file = st.file_uploader("Team CSV", type=["csv"], help="Upload team list with Dialer Name, Email, Full Name, Pool, TL")

# Progress bar and caching
if stringee_file is not None and team_file is not None:
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        status_text.text("🔄 Processing files...")
        progress_bar.progress(20)
        
        final_df_cre, dialers_df, team_size, merged_size = process_files(stringee_file, team_file)
        
        progress_bar.progress(80)
        status_text.text("✅ Processing complete!")
        
        # Debug info sidebar
        with st.sidebar:
            st.markdown("### 📊 Debug Info")
            st.metric("Total Calls Loaded", len(dialers_df))
            st.metric("Matched CREs", len(final_df_cre))
            st.metric("Team Size", team_size)
            st.metric("Merge Match Rate", f"{len(dialers_df)/merged_size*100:.1f}%")
            
            if st.button("🔍 Show unmatched dialers"):
                unmatched = combined_df_2[combined_df_2['CRM ID'].isnull()]['Dialer Name'].value_counts().head(10)
                st.dataframe(unmatched)

        progress_bar.progress(100)
        st.success(f"✅ Dashboard ready! Showing {len(final_df_cre)} CREs with {len(dialers_df)} calls")

        # -----------------------------
        # KPI Cards
        # -----------------------------
        col1, col2, col3, col4 = st.columns(4)
        
        total_dials = final_df_cre[[col for col in final_df_cre.columns if 'Calls' in col]].sum().sum()
        total_talk_cols = [col for col in final_df_cre.columns if 'Talk Time' in col]
        total_connected = final_df_cre[total_talk_cols].count().sum()
        avg_dials = round(total_dials / max(len(final_df_cre),1), 1)
        
        # Calculate average call time properly
        talk_seconds = 0
        for col in total_talk_cols:
            for val in final_df_cre[col]:
                if isinstance(val, str) and val != '00:00:00':
                    h, m, s = map(int, val.split(':'))
                    talk_seconds += h*3600 + m*60 + s
        avg_call_time = round(talk_seconds / max(total_connected,1), 1)

        with col1:
            st.metric("📞 Total Dials", f"{total_dials:,.0f}")
        with col2:
            st.metric("✅ Connected Calls", f"{total_connected:,.0f}")
        with col3:
            st.metric("📊 Avg Dials/CRE", f"{avg_dials:.1f}")
        with col4:
            st.metric("⏱️ Avg Call Time", f"{avg_call_time}s")

        # -----------------------------
        # Filters
        # -----------------------------
        st.subheader("🔧 Filters")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            tl_options = sorted(final_df_cre['TL'].dropna().unique())
            selected_tl = st.multiselect("TL", tl_options, default=tl_options[:min(5, len(tl_options))])
        
        with col2:
            pool_options = sorted(final_df_cre['Pool'].dropna().unique())
            selected_pool = st.multiselect("Pool", pool_options, default=pool_options[:min(5, len(pool_options))])
        
        with col3:
            cre_options = sorted(final_df_cre['Full Name'].dropna().unique())
            selected_cre = st.multiselect("CRE", cre_options, default=cre_options[:min(10, len(cre_options))])

        # Apply filters
        filtered_df = final_df_cre[
            (final_df_cre['TL'].isin(selected_tl)) &
            (final_df_cre['Pool'].isin(selected_pool)) &
            (final_df_cre['Full Name'].isin(selected_cre))
        ].copy()

        # Update KPIs for filtered data
        filtered_total_dials = filtered_df[[col for col in filtered_df.columns if 'Calls' in col]].sum().sum()
        st.metric("Filtered Total Dials", f"{filtered_total_dials:,.0f}")

        # -----------------------------
        # Main Data Table
        # -----------------------------
        st.subheader(f"📈 CRE Summary ({len(filtered_df)} CREs)")
        
        # Make table more readable
        def highlight_max(s):
            is_max = s == s.max()
            return ['background-color: yellow' if v else '' for v in is_max]
        
        styled_df = filtered_df.style.format({
            col: '{:.0f}' for col in filtered_df.columns if 'Calls' in col
        }).apply(highlight_max, subset=[col for col in filtered_df.columns if 'Calls' in col], axis=0)
        
        st.dataframe(styled_df, use_container_width=True, height=600)

    except Exception as e:
        st.error(f"❌ Processing failed: {str(e)}")
        st.exception(e)
        
else:
    st.info("👆 **Please upload both files to get started**")
    st.markdown("""
    ### 📋 **Required Files:**
    - **Stringee Excel**: Contains `Start time`, `Account`, `Call status`, `Answer duration`, etc.
    - **Team CSV**: Contains `Dialer Name`, `Email`, `Full Name`, `Pool`, `TL` columns
    """)
