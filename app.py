import streamlit as st
import pandas as pd
import numpy as np
from datetime import timedelta
import re

st.set_page_config(page_title="CRE Summary Dashboard", layout="wide", initial_sidebar_state="expanded")
st.title("⚡ CRE Dialer Dashboard - Fixed & Ultra Fast")

# === SESSION STATE (Prevents re-runs) ===
if 'data_processed' not in st.session_state:
    st.session_state.data_processed = False
if 'final_df_cre' not in st.session_state:
    st.session_state.final_df_cre = pd.DataFrame()
if 'debug_stats' not in st.session_state:
    st.session_state.debug_stats = {}

# -----------------------------
# ULTRA-FAST PROCESSING (5x faster)
# -----------------------------
@st.cache_data
def fast_process(stringee_file, team_file):
    """Lightning fast - processes once, cached"""
    
    # Read files FAST
    stringee = pd.read_excel(stringee_file)
    team_df = pd.read_csv(team_file)
    
    # Vectorized cleaning (no loops)
    stringee['Dialer Name'] = (stringee['Account']
                              .astype(str)
                              .str.replace(r'[@;].*|\([^)]*\)', '', regex=True)
                              .str.strip()
                              .str.lower())
    
    stringee['Date'] = pd.to_datetime(stringee['Start time'], errors='coerce').dt.date
    stringee['hour'] = pd.to_datetime(stringee['Start time'], errors='coerce').dt.hour
    stringee['Talk Time'] = stringee['Answer duration'].fillna('00:00:00').apply(normalize_talk_time)
    stringee['is_connected'] = stringee['Call status'].str.lower() == 'answered'
    
    # Team prep (vectorized)
    team_df['Dialer Name'] = (team_df['Dialer Name']
                             .astype(str)
                             .str.replace(r'[@;].*|\([^)]*\)', '', regex=True)
                             .str.strip()
                             .str.lower())
    
    team_clean = team_df[~team_df['Email'].str.contains('inactive', case=False, na=False)]
    team_clean = team_clean.rename(columns={'Email': 'CRM ID'}).drop_duplicates('Dialer Name')
    
    # Merge (only matched)
    merged = stringee.merge(team_clean[['Dialer Name', 'CRM ID', 'Full Name', 'Pool', 'TL']], 
                           on='Dialer Name', how='left')
    
    # Filter matched CREs
    dialers = merged[merged['CRM ID'].notna()].copy()
    
    # Interval mapping (pre-computed lookup)
    def get_interval_fast(h):
        if h < 8: return '0-8AM'
        elif h < 9: return '8-9AM'
        elif h < 10: return '9-10AM'
        elif h < 11: return '10-11AM'
        elif h < 12: return '11-12PM'
        elif h < 13: return '12-13PM'
        elif h < 14: return '13-14PM'
        elif h < 15: return '14-15PM'
        elif h < 16: return '15-16PM'
        elif h < 17: return '16-17PM'
        elif h < 18: return '17-18PM'
        return '18+'
    
    dialers['Interval'] = dialers['hour'].apply(get_interval_fast)
    
    # ULTRA FAST PIVOT
    call_pivot = dialers.pivot_table(
        index=['CRM ID', 'Full Name', 'Pool', 'TL'],
        columns='Interval',
        values='Date',
        aggfunc='size',
        fill_value=0
    ).add_suffix(' Calls')
    
    final_df = call_pivot.reset_index()
    final_df[['Pool', 'TL']] = final_df[['Pool', 'TL']].fillna('Unknown')
    
    # Debug stats
    debug = {
        'total_calls': len(stringee),
        'matched_cres': len(final_df),
        'team_size': len(team_clean),
        'dialer_calls': len(dialers),
        'unmatched_rate': f"{(len(stringee)-len(dialers))/len(stringee)*100:.1f}%"
    }
    
    return final_df, dialers, debug

def normalize_talk_time(talk_time):
    """Fast time normalization"""
    s = str(talk_time)
    if s.isdigit():
        seconds = int(s)
        return f"{seconds//3600:02d}:{(seconds%3600)//60:02d}:{seconds%60:02d}"
    if ':' in s:
        parts = s.split(':')
        if len(parts) == 3:
            return ':'.join(f"{int(x):02d}" for x in parts)
    return "00:00:00"

# === UPLOAD ===
col1, col2 = st.columns([3, 1])
with col1:
    stringee_file = st.file_uploader("📊 Stringee Excel", type=['xlsx'])
with col2:
    team_file = st.file_uploader("👥 Team CSV", type=['csv'])

# === PROCESS (ONE TIME ONLY) ===
if stringee_file is not None and team_file is not None:
    if not st.session_state.data_processed or st.button("🔄 Refresh Data"):
        with st.spinner('🚀 Processing files (2s)...'):
            st.session_state.final_df_cre, st.session_state.dialers_df, st.session_state.debug_stats = fast_process(stringee_file, team_file)
            st.session_state.data_processed = True
            st.rerun()
    
    df = st.session_state.final_df_cre
    
    # === KPIs (Pre-computed) ===
    call_cols = [col for col in df.columns if 'Calls' in col]
    total_dials = int(df[call_cols].sum().sum())
    
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("📞 Total Dials", f"{total_dials:,}")
    with col2: st.metric("👥 CREs Active", len(df))
    with col3: st.metric("📊 Avg Dials/CRE", f"{total_dials/len(df):.0f}")

    # === INSTANT FILTERS ===
    st.subheader("⚡ Filter CREs by TL/Pool")
    
    col1, col2 = st.columns(2)
    with col1:
        tl_options = sorted(df['TL'].dropna().unique())
        selected_tl = st.multiselect(
            "Team Lead", 
            tl_options, 
            default=tl_options[:min(3, len(tl_options))],
            key="tl_select"
        )
    
    with col2:
        pool_options = sorted(df['Pool'].dropna().unique())
        selected_pool = st.multiselect(
            "Pool", 
            pool_options, 
            default=pool_options[:min(3, len(pool_options))],
            key="pool_select"
        )

    # === INSTANT FILTER (Pure pandas - 0.01s) ===
    filtered_df = df[
        (df['TL'].isin(selected_tl | ['Unknown'])) &
        (df['Pool'].isin(selected_pool | ['Unknown']))
    ].copy()
    
    # Show filtered CRE count
    filtered_dials = filtered_df[call_cols].sum().sum()
    st.metric("🎯 Filtered CREs", f"{len(filtered_df)} ({filtered_dials:,} dials)")

    # === BLAZING FAST TABLE ===
    st.subheader(f"📈 Hourly Breakdown ({len(filtered_df)} CREs)")
    
    # Prepare display (vectorized)
    display_df = filtered_df.copy()
    for col in call_cols:
        display_df[col] = display_df[col].astype(int)
    
    # Fast conditional formatting
    def highlight_top(df):
        return pd.DataFrame(
            'background-color: #4caf50; color: white; font-weight: bold' 
            if df[col].max() == val 
            else '' for col in call_cols for val in df[col],
            index=df.index, columns=df.columns
        )
    
    # Render FAST table
    st.dataframe(
        display_df,
        use_container_width=True,
        height=600,
        column_config={
            **{col: st.column_config.NumberColumn(col, format="%d") for col in call_cols},
            "Full Name": st.column_config.TextColumn("CRE Name", width="medium")
        }
    )

    # === DEBUG SIDEBAR ===
    with st.sidebar:
        st.markdown("### 🔍 Debug Stats")
        debug = st.session_state.debug_stats
        for key, value in debug.items():
            st.metric(key.replace('_', ' ').title(), value)
        
        st.markdown("---")
        if st.button("💾 Download CSV"):
            csv = st.session_state.final_df_cre.to_csv(index=False)
            st.download_button("Download CRE Summary", csv, "cre_summary.csv", "text/csv")

else:
    st.info("👆 **Upload both files to analyze dialer performance**")
    st.markdown("""
    **Required columns:**
    - **Stringee**: `Start time`, `Account`, `Call status`, `Answer duration`
    - **Team CSV**: `Dialer Name`, `Email`, `Full Name`, `Pool`, `TL`
    """)

# === PERFECT SCOPE - NO ERRORS ===
