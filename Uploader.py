import streamlit as st

from io import StringIO

import numpy as np
import pandas as pd
import plotly.express as px
import yfinance_apis as yf

from allocation import create_global_allocation, analyze_allocation, asset_classes
from parsers import FidelityParser, SchwabParser, VanguardParser


st.set_page_config(page_title='Portfolio Uploader', page_icon='📊', layout='wide')
st.title('Asset Allocation Analyzer')

with st.expander('Adjust Allocation Targets', expanded=False):
    target_cols = st.columns(2)
    target_allocation = create_global_allocation()
    with target_cols[0]:
        target_fig = px.treemap(
            target_allocation.to_df(),
            path=['category', 'ticker'],
            values='weight',
            title='Target Allocation',
            color='category',
        )
        st.plotly_chart(target_fig, use_container_width=True)
    with target_cols[1]:
        preset = st.selectbox('Allocation Presets', ['60/40'])
        apply_preset = st.button('Apply Preset')
        if apply_preset:
            alloc_dsl = st.text_area('Allocation', value='60/40')
        else:
            alloc_dsl = st.text_area('Allocation', value='Something else')
        st.write('Allocation DSL:', alloc_dsl)


def upload_holdings(st_, parser):
    holdings_csv = st_.file_uploader('Upload CSV', type=['csv'], key=parser.brokerage)
    if holdings_csv:
        holdings_f = StringIO(holdings_csv.getvalue().decode('utf-8'))        
        holdings_df = parser.parse_csv(holdings_f)
        return holdings_df
    else:
        return pd.DataFrame()  # empty


holdings_df = None
tabs = st.tabs(['Fidelity', 'Schwab', 'Vanguard', 'README'])
holdings_df = pd.concat([
    upload_holdings(tabs[0], FidelityParser()),
    upload_holdings(tabs[1], SchwabParser()),
    upload_holdings(tabs[2], VanguardParser()),
])

if holdings_df is not None and not holdings_df.empty:
    all_tickers = list(holdings_df[holdings_df['security_type'] == 'Security']['ticker'].unique())
    try:
        with st.spinner('Downloading ticker data...'):
            ticker_df = yf.download_ticker_data(all_tickers, period='5d')
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

    # Portfolio to be rebalanced
    list(target_allocation.to_df()['ticker'].unique())
    source_df = holdings_df[
        holdings_df['ticker'].isin(list(target_allocation.to_df()['ticker'].unique()))
    ].copy()

    # Assign an asset class to each position
    def get_asset_class(ticker):
        asset_class = asset_classes.search(ticker)
        return asset_class.hierarchy()[1] if asset_class else 'Unknown'

    source_df['asset_class'] = source_df['ticker'].apply(get_asset_class)
    holdings_df['asset_class'] = holdings_df['ticker'].apply(get_asset_class)

    summary_cols = st.columns(6)
    summary_cols[0].metric('Total Portfolio', f'${holdings_df["current_value"].sum():,.0f}')
    summary_cols[1].metric('Portfolio to Rebalance', f'${source_df["current_value"].sum():,.0f}')
    summary_cols[2].metric('CDs', f'${holdings_df[holdings_df["security_type"] == "CD"]["current_value"].sum():,.0f}')
    summary_cols[3].metric('Treasuries', f'${holdings_df[holdings_df["security_type"] == "Treasury"]["current_value"].sum():,.0f}')
    summary_cols[4].metric('Money Market', f'${holdings_df[holdings_df["security_type"] == "Money Market"]["current_value"].sum():,.0f}')
    summary_cols[5].metric('Cash', f'${holdings_df[holdings_df["security_type"] == "Cash"]["current_value"].sum():,.0f}')

    cash_to_invest = st.number_input('Additional cash to invest')

    def visualize_drift(key, weights, cash_to_invest, title):
        alloc_df = analyze_allocation(source_df, key, weights, cash_to_invest=cash_to_invest)
        alloc_plot_df = alloc_df[(alloc_df['target_pct'] > 0) | (alloc_df['current_value'] > 0)].reset_index()
        fig1 = px.bar(
            alloc_plot_df.sort_values(by=['current_value']),
            x=key,
            y=['current_value', 'target_value'],
            barmode='group',
            title=f'{title} Targets',
        )
        fig1.update_layout(yaxis=dict(tickformat='$,d', fixedrange=True))
        fig1.update_xaxes(fixedrange=True)
        drift_plot_df = alloc_plot_df.sort_values(by=['action', 'drift_value']).reset_index()
        fig2 = px.bar(
            drift_plot_df,
            x=key,
            y=['drift_value'],
            title=f'{title} Drift',
            text_auto='.2s',
        )
        fig2.update_layout(yaxis=dict(tickformat='$,d', fixedrange=True))
        fig2.update_xaxes(fixedrange=True)
        fig2.update_traces(marker_color=np.where(drift_plot_df['drift_value'] > 0, 'red', 'green'))
        alloc_cols = st.columns(2)
        alloc_cols[0].plotly_chart(fig1, use_container_width=True)
        alloc_cols[1].plotly_chart(fig2, use_container_width=True)
        return alloc_df

    visualize_drift('ticker', target_allocation.get_ticker_weights(), cash_to_invest, 'Ticker')
    visualize_drift('asset_class', target_allocation.get_asset_class_weights(), cash_to_invest, 'Asset Class')

    agg_df = holdings_df[holdings_df['security_type'] == 'Security'][['ticker', 'quantity', 'cost_basis', 'current_value']].groupby('ticker').sum().sort_values(by='current_value').reset_index()
    fig = px.bar(agg_df, x='ticker', y='current_value', text_auto='.2s', title='Tickers')
    fig.update_layout(yaxis=dict(tickformat='$,d', fixedrange=True))
    fig.update_xaxes(fixedrange=True)
    st.plotly_chart(fig, use_container_width=True)

    sunburst_cols = st.columns(2)
    fig = px.sunburst(source_df, path=['asset_class', 'ticker'], values='current_value', title='Core Asset Allocation')
    fig.update_traces(textinfo='label+percent entry')
    sunburst_cols[0].plotly_chart(fig, use_container_width=True)
    fig = px.sunburst(holdings_df, path=['asset_class', 'ticker'], values='current_value', title='Global Asset Allocation')
    fig.update_traces(textinfo='label+percent entry')
    sunburst_cols[1].plotly_chart(fig, use_container_width=True)

    cd_treasuries_df = holdings_df[holdings_df['security_type'].isin(['CD', 'Treasury'])]
    st.dataframe(cd_treasuries_df[['ticker', 'account_name', 'description', 'maturity_date', 'current_value']].sort_values(by='maturity_date').reset_index(drop=True), hide_index=True)

    st.download_button(
        'Download aggregated holdings as CSV',
        data=holdings_df[['account_name', 'asset_class', 'ticker', 'quantity', 'cost_basis', 'current_value']].groupby(['account_name', 'asset_class', 'ticker']).sum().reset_index().to_csv(index=False),
        file_name='portfolio.csv',
    )
    st.expander('Show Holdings', expanded=False).dataframe(holdings_df)
