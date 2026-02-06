# processing.py
import pandas as pd
import numpy as np
import re
from datetime import timedelta

# -----------------------------
# Step 1: Load and format Stringee files
# -----------------------------
def load_stringee(file):
    df = pd.read_excel(file)

    df['Answer duration'] = df['Answer duration'].fillna('00:00:00')
    df['Queue duration'] = df['Queue duration'].fillna('00:00:00')

    df['Start time'] = pd.to_datetime(df['Start time'], errors='coerce')

    df['Date'] = df['Start time'].dt.date
    df['Call Start Time'] = df['Start time'].dt.strftime('%H:%M:%S')

    df['Total Call Duration'] = (
        pd.to_timedelta(df['Queue duration']) +
        pd.to_timedelta(df['Answer duration'])
    ).astype(str).str.split().str[-1]

    df = df.rename(columns={
        'Account': 'Dialer Name',
        'Customer number': 'Number',
        'Call status': 'Call Status',
        'Answer duration': 'Talk Time',
        'Hold duration': 'Hold Time'
    })

    return df[[
        'Date','Dialer Name','Number','Call Status',
        'Call Start Time','Total Call Duration','Talk Time','Hold Time'
    ]]

# -----------------------------
# Step 2: Normalize Talk Time & Call Status
# -----------------------------
def normalize_talk_time(val):
    if re.match(r"^\d+$", str(val)):
        s = int(val)
        return f"{s//3600:02}:{(s%3600)//60:02}:{s%60:02}"
    if re.match(r"^\d+:\d+:\d+$", str(val)):
        h,m,s = map(int,val.split(":"))
        return f"{h:02}:{m:02}:{s:02}"
    return '00:00:00'

def normalize_calls(df):
    df['Talk Time'] = df['Talk Time'].apply(normalize_talk_time)
    df['Total Call Duration'] = df['Total Call Duration'].apply(normalize_talk_time)

    df['Call Status'] = np.where(
        df['Call Status'].str.lower() == 'answered',
        'connected','not connected'
    )

    df['Dialer Name'] = (
        df['Dialer Name']
        .astype(str)
        .str.replace(r'@.*|\(.*', '', regex=True)
        .str.lower().str.strip()
    )

    return df

# -----------------------------
# Step 3: Merge with Team Reference
# -----------------------------
def merge_team(df, team):
    team = team[~team['Email'].str.contains('inactive', case=False, na=False)]
    team['Dialer Name'] = team['Dialer Name'].str.lower().str.strip()
    team = team.rename(columns={'Email':'CRM ID'})

    return df.merge(team, on='Dialer Name', how='left')

# -----------------------------
# Step 4: Calculate Gaps Between Calls
# -----------------------------
def calculate_gaps(df):
    df['Date'] = pd.to_datetime(df['Date'])
    df['Call Start Time'] = pd.to_datetime(
        df['Date'].dt.strftime('%Y-%m-%d') + ' ' + df['Call Start Time']
    )

    df['Total Call Duration'] = pd.to_timedelta(df['Total Call Duration'])

    df = df.sort_values(['CRM ID','Date','Call Start Time']).reset_index(drop=True)

    df['Gap Duration'] = timedelta(0)
    df['Call Gap'] = 'No'

    for i in range(1,len(df)):
        if (
            df.loc[i,'CRM ID'] == df.loc[i-1,'CRM ID'] and
            df.loc[i,'Date'] == df.loc[i-1,'Date']
        ):
            prev_end = df.loc[i-1,'Call Start Time'] + df.loc[i-1,'Total Call Duration']
            gap = df.loc[i,'Call Start Time'] - prev_end
            gap = max(gap, timedelta(0))

            df.loc[i,'Gap Duration'] = gap
            if gap > timedelta(minutes=1):
                df.loc[i,'Call Gap'] = 'Yes'

    return df

# -----------------------------
# Step 5: Convert hh:mm:ss to seconds
# -----------------------------
def to_seconds(x):
    if isinstance(x,pd.Timedelta):
        return int(x.total_seconds())
    h,m,s = map(int,str(x).split(":"))
    return h*3600 + m*60 + s

# -----------------------------
# Step 6: Calculate Daily Metrics
# -----------------------------
def daily_metrics(df):
    df['Talk Sec'] = df['Talk Time'].apply(to_seconds)
    df['Hold Sec'] = df['Hold Time'].apply(to_seconds)
    df['Dur Sec'] = df['Total Call Duration'].apply(to_seconds)
    df['Gap Sec'] = df['Gap Duration'].apply(lambda x: int(x.total_seconds()))

    A = df.groupby(['CRM ID','Date']).agg(
        Total_Dialed_Calls=('Call Status','count'),
        Total_Connected_Calls=('Call Status',lambda x:(x=='connected').sum()),
        Total_Talk_Time=('Talk Sec',lambda x:x[df.loc[x.index,'Call Status']=='connected'].sum()),
        Total_Gap_Duration=('Gap Sec','sum')
    ).reset_index()

    return A

# -----------------------------
# Step 7: Build final CRE pivot table
# -----------------------------
def build_final_df_cre(df):
    df['hour'] = df['Call Start Time'].dt.hour

    def bucket(h):
        return f"{h}:00–{h+1}:00"

    df['Interval'] = df['hour'].apply(bucket)

    calls = pd.pivot_table(
        df,
        index=['CRM ID','Full Name','Pool','TL'],
        columns='Interval',
        values='Date',
        aggfunc='count',
        fill_value=0
    )

    talks = pd.pivot_table(
        df,
        index=['CRM ID','Full Name','Pool','TL'],
        columns='Interval',
        values='Talk Time',
        aggfunc='sum',
        fill_value='00:00:00'
    )

    calls.columns = [f"{c} Calls" for c in calls.columns]
    talks.columns = [f"{c} Talk Time" for c in talks.columns]

    final_df_cre = pd.concat([calls,talks],axis=1).reset_index()

    return final_df_cre

# -----------------------------
# Step 8: Master function to call everything
# -----------------------------
def process_stringee_files(file1, file2, team_file):
    df1 = load_stringee(file1)
    df2 = load_stringee(file2)
    df = pd.concat([df1, df2], ignore_index=True)

    df = normalize_calls(df)

    team = pd.read_csv(team_file)
    df = merge_team(df, team)

    df = calculate_gaps(df)

    dialers_df = df.copy()  # full dialer-level data
    final_df_cre = build_final_df_cre(df)  # pivot CRE summary

    return final_df_cre, dialers_df
