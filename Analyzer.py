import streamlit as st

from io import StringIO

import numpy as np
import pandas as pd
import plotly.express as px
import yfinance_apis as yf

from allocation import single_stocks, asset_classes
from parsers import FidelityParser, SchwabParser, VanguardParser


st.set_page_config(page_title='Asset Analyzer', page_icon='📊', layout='wide')

def upload_holdings(st_, parser):
    holdings_csv = st_.file_uploader(f'Upload {parser.brokerage} CSV', type=['csv'], key=parser.brokerage)
    if holdings_csv:
        holdings_f = StringIO(holdings_csv.getvalue().decode('utf-8'))        
        holdings_df = parser.parse_csv(holdings_f)
        return holdings_df
    else:
        return pd.DataFrame()  # empty

# holdings_df = None

upload_tab, summary_tab, chart_tab = st.tabs(['Upload', 'Summary', 'Charts'])
upload_tab.markdown(
"""
Upload CSV files from Fidelity, Schwab and Vanguard to analyze your portfolio.
""")
holdings_df = pd.concat([
    upload_holdings(upload_tab, FidelityParser()),
    upload_holdings(upload_tab, VanguardParser())
])

# holdings_df = pd.concat([
#     upload_holdings(st.sidebar, FidelityParser()),
#     upload_holdings(st.sidebar, VanguardParser())
# ])

# tabs = st.tabs(['Fidelity', 'Schwab', 'Vanguard', 'Asset Analyzer README'])
# holdings_df = pd.concat([
#     upload_holdings(tabs[0], FidelityParser()),
#     upload_holdings(tabs[1], SchwabParser()),
#     upload_holdings(tabs[2], VanguardParser()),
# ])
# tabs[3].markdown(
# """
# Upload CSV files from Fidelity, Schwab and Vanguard to analyze your portfolio.
# """)

if holdings_df is None or holdings_df.empty:
    for tab in [summary_tab, chart_tab]:
        tab.write('No data to display. Go to the Upload tab to upload some data.')
    st.stop()

@st.cache_data(ttl=600)  # 10 minutes
def cached_ticker_data(tickers):
    return yf.download_ticker_data(tickers, period='5d')

all_tickers = list(holdings_df[holdings_df['security_type'] == 'Security']['ticker'].unique())
try:
    with st.spinner('Downloading ticker data...'):
        ticker_df = cached_ticker_data(all_tickers)
except Exception as e:
    st.error(e)
    st.dataframe(holdings_df)

# Join the ticker data with positions to derive the current value of each position
holdings_df = holdings_df.merge(ticker_df, on='ticker', how='left')
holdings_df['current_value'] = holdings_df['quantity'] * holdings_df['adj_close']

# Fix current value for Money Market, Cash and CDs
mask = holdings_df['security_type'].isin(['Money Market', 'Cash', 'CD', 'Treasury'])
holdings_df.loc[mask, 'current_value'] = holdings_df[mask]['quantity']
holdings_df.loc[mask, 'ticker'] = holdings_df[mask]['security_type']

# Assign an asset class to each position
def get_asset_class(ticker):
    asset_class = asset_classes.search(ticker)
    return asset_class.hierarchy()[1] if asset_class else 'Unknown'

holdings_df['asset_class'] = holdings_df['ticker'].apply(get_asset_class)
holdings_df['core'] = ~holdings_df['ticker'].isin(single_stocks)

# summary_tab, chart_tab = st.tabs(['Summary', 'Charts'])
with summary_tab:
    summary_cols = st.columns(6)
    summary_cols[0].metric('Total Portfolio', f'${holdings_df["current_value"].sum():,.0f}')
    summary_cols[1].metric('Core', f'${holdings_df[holdings_df["core"]]["current_value"].sum():,.0f}')
    summary_cols[2].metric('CDs', f'${holdings_df[holdings_df["security_type"] == "CD"]["current_value"].sum():,.0f}')
    summary_cols[3].metric('Treasuries', f'${holdings_df[holdings_df["security_type"] == "Treasury"]["current_value"].sum():,.0f}')
    summary_cols[4].metric('Money Market', f'${holdings_df[holdings_df["security_type"] == "Money Market"]["current_value"].sum():,.0f}')
    summary_cols[5].metric('Cash', f'${holdings_df[holdings_df["security_type"] == "Cash"]["current_value"].sum():,.0f}')

    core_only = st.checkbox('Exclude single stocks', value=True)

    tree_col, pie_col = st.columns([2, 1])
    asset_class_tree_map = tree_col.empty()
    account_fig = px.treemap(
        holdings_df[holdings_df['core']] if core_only else holdings_df,
        path=['asset_class', 'ticker'],
        values='current_value',
        title='Holdings by Asset Class (excl. single stocks)' if core_only else 'Holdings by Asset Class',
        height=600,
    )
    account_fig.update_layout(margin=dict(l=0, r=0, t=40, b=40))
    account_fig.data[0].textinfo = 'label+text+value+percent root+percent parent'
    asset_class_tree_map.plotly_chart(account_fig, use_container_width=True)

    pie_fig = px.pie(
        holdings_df[holdings_df['core']] if core_only else holdings_df,
        values='current_value',
        names='asset_class',
        title='Asset Allocation (excl. single stocks)' if core_only else 'Asset Allocation',
    )
    pie_fig.update_layout(legend=dict(
        yanchor="top",
        y=0.99,
        xanchor="left",
        x=0.01
    ))
    pie_fig.update_layout(margin=dict(l=0, r=0, t=40, b=40))
    pie_col.plotly_chart(pie_fig)

with chart_tab:
    a, b = st.columns(2)
    with a:
        y_axis = st.selectbox('Y-Axis', ['account_name', 'asset_class', 'ticker'], index=0)
    with b:
        color_by = st.selectbox('Color By', ['account_name', 'asset_class', 'ticker'], index=2)
    c, d, e = st.columns(3)
    with c:
        all_tickers = sorted(list(holdings_df['ticker'].unique()))
        incl_tickers = st.multiselect('Only these Tickers', all_tickers)
    with d:
        all_asset_classes = sorted(list(holdings_df['asset_class'].unique()))
        incl_asset_classes = st.multiselect('Only these Asset Classes', all_asset_classes)
    with e:
        all_accounts = sorted(str(s) for s in set(holdings_df['account_name']))
        incl_accounts = st.multiselect('Only these Accounts', all_accounts)
    excl_single_stocks = st.checkbox('Excl. single stocks', value=True)
    single_stock_filter = ~holdings_df['ticker'].isin(single_stocks) | bool(not excl_single_stocks)
    ticker_filter = holdings_df['ticker'].isin(incl_tickers) | bool(not incl_tickers)
    asset_class_filter = holdings_df['asset_class'].isin(incl_asset_classes) | bool(not incl_asset_classes)
    account_filter = holdings_df['account_name'].isin(incl_accounts) | bool(not incl_accounts)    
    chart_df = holdings_df[single_stock_filter & ticker_filter & asset_class_filter & account_filter]
    grouper = list(set([y_axis, color_by]))
    agg_df = chart_df[grouper + ['quantity', 'cost_basis', 'current_value']].groupby(grouper).sum().reset_index()

    # bar_col, pie_col = st.columns([2, 1])
    fig = px.bar(
        agg_df,
        x='current_value', 
        y=y_axis, 
        color=color_by, 
        text_auto='.2s', 
        title=f'Per {y_axis}, broken out by {color_by}',
    )
    fig.update_layout(
        xaxis=dict(tickformat='$,d', fixedrange=True),
        yaxis={'categoryorder':'total ascending'},
        margin=dict(l=0, r=0, t=40, b=40)
    )
    st.plotly_chart(fig, use_container_width=True)
    color_fig = px.pie(
        agg_df,
        values='current_value',
        names=color_by,
        title=f'Aggregated by {color_by}',
    )
    color_fig.update_layout(legend=dict(
        yanchor="top",
        y=0.99,
        xanchor="left",
        x=0.01
    ))
    color_fig.update_layout(margin=dict(l=0, r=0, t=40, b=40))
    st.plotly_chart(color_fig, use_container_width=True)

st.download_button(
    'Download aggregated holdings as CSV',
    data=holdings_df[['account_name', 'asset_class', 'ticker', 'quantity', 'cost_basis', 'current_value']].groupby(['account_name', 'asset_class', 'ticker']).sum().reset_index().to_csv(index=False),
    file_name='portfolio.csv',
)
st.expander('Show Holdings', expanded=False).dataframe(holdings_df)
