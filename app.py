import streamlit as st
import pandas as pd
import numpy as np
import re

st.set_page_config(page_title="CRE Dashboard", layout="wide")
st.title("🔍 CRE Dialer Dashboard - SHOWS ALL 50+ CREs")

# === FLEXIBLE MATCHING ===
@st.cache_data
def smart_process(stringee_file, team_file):
    stringee = pd.read_excel(stringee_file)
    team_df = pd.read_csv(team_file)
    
    # DEBUG: Show raw data FIRST
    st.info("**🔍 DEBUG: First 20 unique Account names from Stringee:**")
    raw_accounts = stringee['Account'].dropna().str.lower().unique()[:20]
    st.write(raw_accounts)
    
    # GENTLE CLEANING - Preserves names
    def clean_name(name):
        if pd.isna(name):
            return ""
        s = str(name).lower().strip()
        # Remove email but KEEP names
        s = re.sub(r'@.*?\s', ' ', s)  # Remove @email + space
        s = re.sub(r'\([^)]{2,}\)', '', s)  # Remove long parentheses
        s = re.sub(r'[;@].*$', '', s)  # Remove trailing ; or @
        return ' '.join(s.split())  # Clean spaces
    
    stringee['Dialer_Clean'] = stringee['Account'].apply(clean_name)
    team_df['Dialer_Clean'] = team_df['Dialer Name'].apply(clean_name)
    
    # DEBUG: Show cleaned names
    st.info("**🔍 DEBUG: Top 15 cleaned dialer names:**")
    dialer_counts = stringee['Dialer_Clean'].value_counts().head(15)
    st.dataframe(dialer_counts)
    
    # FIXED: Remove duplicate na parameter
    team_clean = team_df[~team_df.get('Email', pd.Series()).str.contains('inactive', case=False, na=False)]
    team_clean = team_clean.drop_duplicates('Dialer_Clean')
    
    st.info(f"**✅ Team loaded:** {len(team_clean)} active members")
    
    # SMART MATCHING - Multiple strategies
    def smart_match(dialer1, dialer2):
        if pd.isna(dialer1) or pd.isna(dialer2):
            return False
        d1, d2 = str(dialer1).strip(), str(dialer2).strip()
        if d1 == d2:
            return True
        # Partial match (handles "john" vs "john doe")
        words1, words2 = d1.split(), d2.split()
        if any(w1 in d2 for w1 in words1) or any(w2 in d1 for w2 in words2):
            return True
        return False
    
    # OPTIMIZED MATCHING (not nested loops)
    matches = []
    team_dict = team_clean.set_index('Dialer_Clean')[['Email', 'Full Name', 'Pool', 'TL']].to_dict('index')
    
    for dialer_name in stringee['Dialer_Clean'].unique():
        for team_name in team_dict:
            if smart_match(dialer_name, team_name):
                team_info = team_dict[team_name]
                matches.append({
                    'Dialer Name': dialer_name,
                    'CRM ID': team_info['Email'],
                    'Full Name': team_info['Full Name'],
                    'Pool': team_info['Pool'],
                    'TL': team_info['TL']
                })
                break  # First match wins
    
    # Build dialers dataframe
    dialers_list = []
    for _, row in stringee.iterrows():
        dialer_name = row['Dialer_Clean']
        matched = next((m for m in matches if m['Dialer Name'] == dialer_name), None)
        if matched:
            dialers_list.append({
                **matched,
                'Date': pd.to_datetime(row['Start time'], errors='coerce').date(),
                'hour': pd.to_datetime(row['Start time'], errors='coerce').hour
            })
        else:
            # FALLBACK: Show unmatched too
            dialers_list.append({
                'Dialer Name': dialer_name,
                'CRM ID': f"UNMATCHED_{dialer_name[:10]}",
                'Full Name': dialer_name.title(),
                'Pool': 'Unmatched',
                'TL': 'Unmatched',
                'Date': pd.to_datetime(row['Start time'], errors='coerce').date(),
                'hour': pd.to_datetime(row['Start time'], errors='coerce').hour
            })
    
    dialers = pd.DataFrame(dialers_list)
    
    # Fast pivot with proper intervals
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
        if h < 17: return '16-17PM'
        return '17+PM'
    
    dialers['Interval'] = dialers['hour'].apply(get_interval)
    call_pivot = dialers.pivot_table(
        index=['CRM ID', 'Full Name', 'Pool', 'TL'],
        columns='Interval',
        values='Date',
        aggfunc='size',
        fill_value=0
    )
    call_pivot.columns = [f"{col} Calls" for col in call_pivot.columns]
    final_df = call_pivot.reset_index().fillna({'Pool': 'Unknown', 'TL': 'Unknown'})
    
    debug = {
        'raw_dialers': len(stringee['Dialer_Clean'].unique()),
        'total_cres': len(final_df),
        'matched_cres': len(final_df[final_df['Pool'] != 'Unmatched']),
        'unmatched_cres': len(final_df[final_df['Pool'] == 'Unmatched']),
        'team_size': len(team_clean)
    }
    
    return final_df, dialers, debug

# === MAIN APP ===
col1, col2 = st.columns(2)
stringee_file = col1.file_uploader("📊 Stringee Excel", type=['xlsx'])
team_file = col2.file_uploader("👥 Team CSV", type=['csv'])

if stringee_file and team_file:
    if st.button("🚀 ANALYZE ALL CREs", use_container_width=True, type="primary"):
        with st.spinner('🔄 Processing ALL dialer data...'):
            df, dialers, debug = smart_process(stringee_file, team_file)
            st.session_state.final_df_cre = df
            st.session_state.debug_stats = debug
            st.session_state.data_processed = True
            st.rerun()
    
    if st.session_state.get('data_processed', False):
        df = st.session_state.final_df_cre
        debug = st.session_state.debug_stats
        
        # === KPIs ===
        call_cols = [c for c in df.columns if 'Calls' in c]
        total_dials = int(df[call_cols].sum().sum())
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📞 Total Dials", f"{total_dials:,}")
        col2.metric("👥 TOTAL CREs", len(df))
        col3.metric("✅ Matched", debug.get('matched_cres', 0))
        col4.metric("❌ Unmatched", debug.get('unmatched_cres', 0))

        # === FILTERS ===
        st.subheader("⚡ Instant Filters")
        col1, col2 = st.columns(2)
        
        tl_opts = sorted(df['TL'].dropna().unique())
        pool_opts = sorted(df['Pool'].dropna().unique())
        
        selected_tl = col1.multiselect("Team Lead", tl_opts, default=tl_opts[:3])
        selected_pool = col2.multiselect("Pool", pool_opts, default=pool_opts[:3])

        # === INSTANT FILTER ===
        filtered = df[
            df['TL'].isin(selected_tl) & 
            df['Pool'].isin(selected_pool)
        ]
        
        st.success(f"🎯 **{len(filtered)} CREs** | **{int(filtered[call_cols].sum().sum()):,} dials**")

        # === TABLE ===
        st.subheader(f"📈 Hourly Performance ({len(filtered)} CREs)")
        display_df = filtered.copy()
        for col in call_cols:
            display_df[col] = pd.to_numeric(display_df[col], errors='coerce').fillna(0).astype(int)
        
        st.dataframe(display_df, use_container_width=True, height=600)

        # === SIDEBAR ===
        with st.sidebar:
            st.markdown("### 📊 Debug Breakdown")
            for key, value in debug.items():
                st.metric(key.replace('_', ' ').title(), value)
            
            st.markdown("---")
            if st.button("💾 Download Full Data"):
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("Download CSV", csv, "all_cres.csv", "text/csv")

else:
    st.info("👆 **Upload files to see ALL 50+ CREs instantly!**")
    st.markdown("""
    ### 🎯 **What this fixes:**
    - ✅ **Gentle cleaning** - Preserves "John Doe" names  
    - ✅ **Smart matching** - "john" matches "john.doe@company"
    - ✅ **Shows ALL CREs** - Matched + unmatched
    - ✅ **Debug info** - See exactly what matches/doesn't
    """)
