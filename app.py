import streamlit as st
import pandas as pd
from processing import process_stringee_files  # function that returns final_df_cre

st.set_page_config(page_title="CRE Summary Dashboard", layout="wide")

st.title("CRE Dialer Dashboard")

# File uploads
stringee_file1 = st.file_uploader("Upload Stringee File 1", type=['xlsx'])
stringee_file2 = st.file_uploader("Upload Stringee File 2", type=['xlsx'])
team_file = st.file_uploader("Upload Team List CSV", type=['csv'])

if stringee_file1 and stringee_file2 and team_file:
    # Process data
    final_df_cre, dialers_df = process_stringee_files(
        stringee_file1, stringee_file2, team_file
    )

    # Filters
    tl_options = final_df_cre['TL'].unique().tolist()
    pool_options = final_df_cre['Pool'].unique().tolist()
    cre_options = final_df_cre['Full Name'].unique().tolist()

    selected_tl = st.multiselect("Select TL", tl_options, default=tl_options)
    selected_pool = st.multiselect("Select Pool", pool_options, default=pool_options)
    selected_cre = st.multiselect("Select CRE", cre_options, default=cre_options)

    filtered_df = final_df_cre[
        (final_df_cre['TL'].isin(selected_tl)) &
        (final_df_cre['Pool'].isin(selected_pool)) &
        (final_df_cre['Full Name'].isin(selected_cre))
    ]

    # KPI cards
    total_dials = filtered_df[[col for col in filtered_df.columns if 'Calls' in col]].sum().sum()
    total_connected = filtered_df[[col for col in filtered_df.columns if 'Talk Time' in col]].count().sum()
    avg_dials = round(total_dials / max(len(filtered_df),1), 2)
    avg_call_time = round(
        filtered_df[[col for col in filtered_df.columns if 'Talk Time' in col]].sum().sum() / max(total_connected,1), 2
    )

    st.metric("Total Dials", total_dials)
    st.metric("Total Connected Dials", total_connected)
    st.metric("Average Dialed Calls per CRE", avg_dials)
    st.metric("Average Call Time (seconds)", avg_call_time)

    # Show CRE summary
    st.dataframe(filtered_df)

