import streamlit as st
import pandas as pd
import numpy as np
import re

st.set_page_config(page_title="CRE Dashboard", layout="wide")
st.title("🔍 CRE Dialer Dashboard - 2 FILES + ALL 50+ CREs")

@st.cache_data
def smart_process(file1, file2, team_file):
    # Read BOTH Stringee files
    df1 = pd.read_excel(file1)
    df2 = pd.read_excel(file2)
    team_df = pd.read_csv(team_file)
    
    # COMBINE both Stringee files
    stringee = pd.concat([df1, df2], ignore_index=True)
    
    st.info(f"📊 **Loaded {len(stringee):,} total calls** from 2 files")
    
    # GENTLE CLEANING
    def clean_name(name):
        if pd.isna(name): return ""
        s = str(name).lower().strip()
        s = re.sub(r'@.*?\s', ' ', s)  # Remove email
        s = re.sub(r'\([^)]{2,}\)', '', s)  # Remove long parens
        s = re.sub(r'[;@].*$', '', s)  # Remove trailing
        return ' '.join(s.split())
    
    stringee['Dialer_Clean'] = stringee['Account'].apply(clean_name)
    team_df['Dialer_Clean'] = team_df['Dialer Name'].apply(clean_name)
    
    # Team prep
    team_clean = team_df[~team_df.get('Email', pd.Series()).str.contains('inactive', case=False, na=False)]
    team_clean = team_clean.drop_duplicates('Dialer_Clean')
    
    # DEBUG: Show actual names
    st.info("**🔍 Top 20 dialer names from BOTH files:**")
    st.dataframe(stringee['Dialer_Clean'].value_counts().head(20))
    
    # SMART MATCHING
    def smart_match(d1, d2):
        if pd.isna(d1) or pd.isna(d2): return False
        d1, d2 = str(d1).strip(), str(d2).strip()
        if d1 == d2: return True
        words1, words2 = d1.split(), d2.split()
        return any(w1 in d2 for w1 in words1) or any(w2 in d1 for w2 in words2)
    
    # Create matches dictionary
    matches = {}
    for dialer in stringee['Dialer_Clean'].unique():
        for team_name in team_clean['Dialer_Clean']:
            if smart_match(dialer, team_name):
                matches[dialer] = team_clean[team_clean['Dialer_Clean'] == team_name].iloc[0]
                break
    
    # Build dialers
    dialers_list = []
    for _, row in stringee.iterrows():
        dialer = row['Dialer_Clean']
        if dialer in matches:
            team_row = matches[dialer]
            dialers_list.append({
                'CRM ID': team_row['Email'],
                'Full Name': team_row.get('Full Name', dialer.title()),
                'Pool': team_row.get('Pool', 'Unknown'),
                'TL': team_row.get('TL', 'Unknown'),
                'Date': pd.to_datetime(row['Start time'], errors='coerce').date(),
                'hour': pd.to_datetime(row['Start time'], errors='coerce').hour
            })
        else:
            dialers_list.append({
                'CRM ID': f"UNMATCHED_{dialer[:8]}",
                'Full Name': dialer.title(),
                'Pool': 'Unmatched',
                'TL': 'Unmatched',
                'Date': pd.to_datetime(row['Start time'], errors='coerce').date(),
                'hour': pd.to_datetime(row['Start time'], errors='coerce').hour
            })
    
    dialers = pd.DataFrame(dialers_list)
    
    # PROPER INTERVALS
    def get_interval(h):
        if pd.isna(h): return 'Unknown'
        h = int(h)
        if h < 8: return '0-8AM'
        if h < 9: return '8-9AM'
        if h < 10: return '9-10AM'
        if h < 11: return '10-11AM'
        if h < 12: return '11-12PM'
        if h < 13: return '12-13PM'
        if h < 14: return '13-14PM'
        if h < 15: return '14-15PM'
        if h < 16: return '15-16PM'
        return '16+PM'
    
    dialers['Interval'] = dialers['hour'].apply(get_interval)
    
    # FINAL PIVOT
    pivot = dialers.pivot_table(
        index=['CRM ID', 'Full Name', 'Pool', 'TL'],
        columns='Interval',
        values='Date',
        aggfunc='size',
        fill_value=0
    )
    pivot.columns = [f"{col} Calls" for col in pivot.columns]
    final_df = pivot.reset_index()
    
    debug = {
        'total_calls': len(stringee),
        'unique_dialers': len(stringee['Dialer_Clean'].unique()),
        'total_cres': len(final_df),
        'matched': len(final_df[final_df['Pool'] != 'Unmatched']),
        'unmatched': len(final_df[final_df['Pool'] == 'Unmatched']),
        'team_size': len(team_clean)
    }
    
    return final_df, dialers, debug

# === 2 FILES UPLOAD (ORIGINAL FORMAT) ===
col1, col2, col3 = st.columns([1,1,2])
stringee_file1 = col1.file_uploader("📊 **Stringee File 1** (.xlsx)", type=['xlsx'])
stringee_file2 = col2.file_uploader("📊 **Stringee File 2** (.xlsx)", type=['xlsx'])
team_file = col3.file_uploader("👥 **Team CSV**", type=['csv'])

if stringee_file1 and stringee_file2 and team_file:
    if st.button("🚀 PROCESS BOTH FILES", type="primary", use_container_width=True):
        with st.spinner('🔄 Combining 2 Excel files...'):
            df, dialers, debug = smart_process(stringee_file1, stringee_file2, team_file)
            st.session_state.df = df
            st.session_state.debug = debug
            st.session_state.processed = True
            st.rerun()
    
    if st.session_state.get('processed', False):
        df = st.session_state.df
        debug = st.session_state.debug
        
        # === DASHBOARD ===
        call_cols = [c for c in df.columns if 'Calls' in c]
        total_dials = int(df[call_cols].sum().sum())
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📞 Total Dials", f"{total_dials:,}")
        col2.metric("👥 TOTAL CREs", len(df))
        col3.metric("✅ Matched", debug['matched'])
        col4.metric("📈 Coverage", f"{debug['matched']/len(df)*100:.0f}%")
        
        # === FILTERS ===
        col1, col2 = st.columns(2)
        tl_opts = sorted(df['TL'].dropna().unique())
        pool_opts = sorted(df['Pool'].dropna().unique())
        
        selected_tl = col1.multiselect("👤 Team Lead", tl_opts, default=tl_opts[:3])
        selected_pool = col2.multiselect("🏊 Pool", pool_opts, default=pool_opts[:3])
        
        # FILTER
        filtered = df[df['TL'].isin(selected_tl) & df['Pool'].isin(selected_pool)]
        st.success(f"🎯 **{len(filtered)} CREs** | **{int(filtered[call_cols].sum().sum()):,} calls**")
        
        # TABLE
        display_df = filtered[call_cols + ['Full Name', 'Pool', 'TL']].copy()
        for col in call_cols:
            display_df[col] = pd.to_numeric(display_df[col], errors='coerce').fillna(0).astype(int)
        
        st.subheader(f"📊 Hourly Breakdown ({len(filtered)} CREs)")
        st.dataframe(display_df, use_container_width=True, height=500)
        
        # SIDEBAR
        with st.sidebar:
            st.markdown("### 🔍 Debug")
            for k, v in debug.items():
                st.metric(k.replace('_', ' ').title(), v)
            st.markdown("---")
            st.download_button("💾 Download", df.to_csv(index=False).encode(), "all_cre.csv")

else:
    st.info("👆 **Upload BOTH Stringee Excel files + Team CSV**")
    st.markdown("""
    **📋 Expected format:**
    - **Stringee Excel**: `Start time`, `Account`, `Answer duration`
    - **Team CSV**: `Dialer Name`, `Email`, `Full Name`, `Pool`, `TL`
    """)
