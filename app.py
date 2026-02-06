import streamlit as st
import pandas as pd
import numpy as np
from datetime import timedelta
import re

st.set_page_config(page_title="CRE Summary Dashboard", layout="wide", initial_sidebar_state="expanded")
st.title("⚡ CRE Dialer Dashboard - PERFECT")

# === SESSION STATE ===
if 'data_processed' not in st.session_state:
    st.session_state.data_processed = False
if 'final_df_cre' not in st.session_state:
    st.session_state.final_df_cre = pd.DataFrame()
if 'debug_stats' not in st.session_state:
    st.session_state.debug_stats = {}

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

@st.cache_data
def fast_process(stringee_file, team_file):
    """Lightning-fast processing"""
    stringee = pd.read_excel(stringee_file)
    team_df = pd.read_csv(team_file)
    
    # Fast vectorized cleaning
    stringee['Dialer Name'] = (stringee['Account']
                              .astype(str)
                              .str.replace(r'[@;].*|\([^)]*\)', '', regex=True)
                              .str.strip()
                              .str.lower())
    
    stringee['Date'] = pd.to_datetime(stringee['Start time'], errors='coerce').dt.date
    stringee['hour'] = pd.to_datetime(stringee['Start time'], errors='coerce').dt.hour
    stringee['Talk Time'] = stringee['Answer duration'].fillna('00:00:00').apply(normalize_talk_time)
    
    # Team cleaning
    team_df['Dialer Name'] = (team_df['Dialer Name']
                             .astype(str)
                             .str.replace(r'[@;].*|\([^)]*\)', '', regex=True)
                             .str.strip()
                             .str.lower())
    
    team_clean = team_df[~team_df.get('Email', pd.Series()).str.contains('inactive', case=False, na=False)]
    team_clean = team_clean.rename(columns={'Email': 'CRM ID'}).drop_duplicates('Dialer Name')
    
    # Merge
    merged = stringee.merge(team_clean[['Dialer Name', 'CRM ID', 'Full Name', 'Pool', 'TL']], 
                           on='Dialer Name', how='left')
    
    dialers = merged[merged['CRM ID'].notna()].copy()
    
    # Fast intervals
    def get_interval_fast(h):
        if h < 8: return '0-8AM'
        if h < 9: return '8-9AM'
        if h < 10: return '9-10AM'
        if h < 11: return '10-11AM'
        if h < 12: return '11-12PM'
        if h < 13: return '12-13PM'
        if h < 14: return '13-14PM'
        if h < 15: return '14-15PM'
        if h < 16: return '15-16PM'
        if h < 17: return '16-17PM'
        if h < 18: return '17-18PM'
        return '18+'
    
    dialers['Interval'] = dialers['hour'].apply(get_interval_fast)
    
    # Ultra-fast pivot
    call_pivot = dialers.pivot_table(
        index=['CRM ID', 'Full Name', 'Pool', 'TL'],
        columns='Interval',
        values='Date',
        aggfunc='size',
        fill_value=0
    ).add_suffix(' Calls')
    
    final_df = call_pivot.reset_index().fillna({'Pool': 'Unknown', 'TL': 'Unknown'})
    
    debug = {
        'total_calls': len(stringee),
        'matched_cres': len(final_df),
        'team_size': len(team_clean),
        'dialer_calls': len(dialers),
        'match_rate': f"{len(dialers)/len(stringee)*100:.1f}%"
    }
    
    return final_df, dialers, debug

# === UPLOAD ===
col1, col2 = st.columns([3, 1])
with col1:
    st.markdown("### 📊 Upload Files")
    stringee_file = st.file_uploader("Stringee Excel", type=['xlsx'])
with col2:
    team_file = st.file_uploader("Team CSV", type=['csv'])

# === PROCESS ===
if stringee_file is not None and team_file is not None:
    if not st.session_state.data_processed or st.button("🔄 Refresh", use_container_width=True):
        with st.spinner('⚡ Processing...'):
            st.session_state.final_df_cre, st.session_state.dialers_df, st.session_state.debug_stats = fast_process(stringee_file, team_file)
            st.session_state.data_processed = True
    
    df = st.session_state.final_df_cre
    
    # === KPIs ===
    call_cols = [col for col in df.columns if 'Calls' in col]
    total_dials = int(df[call_cols].sum().sum())
    
    col1, col2, col3 = st.columns(3)
    col1.metric("📞 Total Dials", f"{total_dials:,}")
    col2.metric("👥 Active CREs", len(df))
    col3.metric("📊 Avg/CRE", f"{total_dials/len(df):.0f}")

    # === FILTERS (Instant) ===
    st.markdown("---")
    st.subheader("⚡ Filter by TL & Pool")
    
    col1, col2 = st.columns(2)
    with col1:
        tl_options = sorted(df['TL'].dropna().unique())
        selected_tl = st.multiselect("Team Lead", tl_options, 
                                   default=tl_options[:2] if len(tl_options) > 2 else tl_options)
    
    with col2:
        pool_options = sorted(df['Pool'].dropna().unique())
        selected_pool = st.multiselect("Pool", pool_options, 
                                     default=pool_options[:2] if len(pool_options) > 2 else pool_options)

    # === FILTER DATA (0.01s) ===
    mask_tl = df['TL'].isin(selected_tl)
    mask_pool = df['Pool'].isin(selected_pool)
    filtered_df = df[mask_tl & mask_pool].copy()
    
    filtered_dials = int(filtered_df[call_cols].sum().sum())
    st.success(f"🎯 **{len(filtered_df)} CREs** | **{filtered_dials:,} dials**")

    # === PERFECT TABLE ===
    st.markdown("---")
    st.subheader(f"📈 Hourly Performance ({len(filtered_df)} CREs)")
    
    # Fast numeric conversion
    display_df = filtered_df.copy()
    for col in call_cols:
        display_df[col] = pd.to_numeric(display_df[col], errors='coerce').fillna(0).astype(int)
    
    # Simple fast styling
    def highlight_maxes(df):
        styles = pd.DataFrame('', index=df.index, columns=df.columns)
        for col in call_cols:
            max_idx = df[col].idxmax()
            if pd.notna(max_idx):
                styles.at[max_idx, col] = 'background-color: #4CAF50; color: white; font-weight: bold'
        return styles
    
    # Ultra-fast display
    styled_df = (display_df.style
                .apply(highlight_maxes, axis=None)
                .format({col: '{:,.0f}' for col in call_cols}))
    
    st.dataframe(styled_df, use_container_width=True, height=700)

    # === SIDEBAR ===
    with st.sidebar:
        st.markdown("### 🔍 Debug Info")
        debug = st.session_state.debug_stats
        col1, col2 = st.columns(2)
        col1.metric("📊 Total Calls", f"{debug.get('total_calls', 0):,}")
        col2.metric("✅ Matched CREs", debug.get('matched_cres', 0))
        col1.metric("👥 Team Size", debug.get('team_size', 0))
        col2.metric("📈 Match Rate", debug.get('match_rate', '0%'))
        
        st.markdown("---")
        if st.button("💾 Download Results"):
            csv = st.session_state.final_df_cre.to_csv(index=False).encode()
            st.download_button(
                "Download CSV", 
                csv, 
                "cre_summary.csv", 
                "text/csv"
            )

else:
    st.info("👆 **Upload Stringee Excel + Team CSV**")
    st.markdown("""
    **Stringee needs:** `Start time`, `Account`, `Call status`, `Answer duration`  
    **Team CSV needs:** `Dialer Name`, `Email`, `Full Name`, `Pool`, `TL`
    """)
