import streamlit as st

from io import StringIO

import numpy as np
import pandas as pd
import plotly.express as px
import yfinance_apis as yf

from allocation import create_global_allocation, analyze_allocation
from parsers import parse_fidelity


st.set_page_config(page_title='Fidelity Uploader', layout='wide')
holdings_df = None
tabs = st.tabs(['Fidelity', 'Schwab'])
with tabs[0]:
    holdings_csv = st.file_uploader('Upload CSV', type=['csv'])
    if holdings_csv:
        holdings_f = StringIO(holdings_csv.getvalue().decode('utf-8'))
        holdings_df = parse_fidelity(holdings_f)

if holdings_df is None or holdings_df.empty:
    st.stop()

all_tickers = list(holdings_df[holdings_df['security_type'] == 'Security']['ticker'].unique())
try:
    with st.spinner('Downloading ticker data...'):
        ticker_df = yf.download_ticker_data(all_tickers, period='5d')
except Exception as e:
    st.error(e)
    st.dataframe(holdings_df)
    st.stop()

# Join the ticker data with positions to derive the current value of each position
holdings_df = holdings_df.merge(ticker_df, on='ticker', how='left')
holdings_df['current_value'] = holdings_df['quantity'] * holdings_df['adj_close']

# Fix current value for Money Market, Cash and CDs
mask = holdings_df['security_type'].isin(['Money Market', 'Cash', 'CD', 'Treasury'])
holdings_df.loc[mask, 'current_value'] = holdings_df[mask]['quantity']

# Core portfolio
core_df = pd.concat([
    holdings_df[
        holdings_df['ticker'].isin([
            'AVDV',
            'AVES',
            'AVLV',
            'AVRE',
            'AVUV',
            'DFIV',
            'DUHP',
            'ITOT',
            'QQQM',
            'COWZ',
            'VEA',
            'VTEB',
            'VWO',
            'TBIL',
            'VGSLX',
            # Legacy
            'QQQJ',
            'RPV',
            'SCHD',
        ])
    ],
    holdings_df[
        holdings_df['security_type'].isin(['CD', 'Treasury'])
    ].assign(ticker='CD / Treasury'),
])

summary_cols = st.columns(6)
summary_cols[0].metric('Total Portfolio', f'${holdings_df["current_value"].sum():,.0f}')
summary_cols[1].metric('Core Portfolio', f'${core_df["current_value"].sum():,.0f}')
summary_cols[2].metric('CDs', f'${holdings_df[holdings_df["security_type"] == "CD"]["current_value"].sum():,.0f}')
summary_cols[3].metric('Treasuries', f'${holdings_df[holdings_df["security_type"] == "Treasury"]["current_value"].sum():,.0f}')
summary_cols[4].metric('Money Market', f'${holdings_df[holdings_df["security_type"] == "Money Market"]["current_value"].sum():,.0f}')
summary_cols[5].metric('Cash', f'${holdings_df[holdings_df["security_type"] == "Cash"]["current_value"].sum():,.0f}')

weighted_tickers = create_global_allocation().collect_weights()
ticker_target = [(ticker, weight) for ticker, weight in weighted_tickers]
cash_to_invest = st.number_input('Cash to invest')
alloc_cols = st.columns(2)
alloc_df = analyze_allocation(
    core_df,
    'ticker',
    ticker_target,
    cash_to_invest=cash_to_invest,
)

alloc_plot_df = alloc_df[(alloc_df['target_pct'] > 0) | (alloc_df['current_value'] > 0)].reset_index()
fig = px.bar(
    alloc_plot_df.sort_values(by=['current_value']),
    x='ticker',
    y=['current_value', 'target_value'],
    barmode='group',
    title='Ticker Allocation Targets',
)
fig.update_layout(yaxis=dict(tickformat='$,d', fixedrange=True))
fig.update_xaxes(fixedrange=True)
alloc_cols[0].plotly_chart(fig, use_container_width=True)
drift_plot_df = alloc_plot_df.sort_values(by=['action', 'drift_value']).reset_index()
fig = px.bar(
    drift_plot_df,
    x='ticker',
    y=['drift_value'],
    title='Ticker Drift',
    text_auto='.2s',
)
fig.update_layout(yaxis=dict(tickformat='$,d', fixedrange=True))
fig.update_xaxes(fixedrange=True)
fig.update_traces(marker_color=np.where(drift_plot_df['drift_value'] > 0, 'red', 'green'))
alloc_cols[1].plotly_chart(fig, use_container_width=True)

target_fig = px.treemap(
    create_global_allocation().to_df(),
    path=['category', 'ticker'],
    values='weight',
    title='Target Allocation',
    color='category',
)
st.plotly_chart(target_fig, use_container_width=True)

agg_df = holdings_df[holdings_df['security_type'] == 'Security'][['ticker', 'quantity', 'cost_basis', 'current_value']].groupby('ticker').sum().sort_values(by='current_value').reset_index()
fig = px.bar(agg_df, x='ticker', y='current_value', text_auto='.2s', title='Tickers')
fig.update_layout(yaxis=dict(tickformat='$,d', fixedrange=True))
fig.update_xaxes(fixedrange=True)
st.plotly_chart(fig, use_container_width=True)

st.download_button(
    'Download aggregated holdings as CSV',
    data=holdings_df[['ticker', 'quantity', 'cost_basis']].groupby('ticker').sum().reset_index().to_csv(index=False),
    file_name='portfolio.csv',
)

st.expander('Show Holdings', expanded=False).dataframe(holdings_df)
