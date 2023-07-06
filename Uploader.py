import streamlit as st

from io import StringIO

import yfinance_apis as yf

from parsers import parse_fidelity


st.set_page_config(page_title='Fidelity Uploader', layout='wide')
holdings_df = None
tabs = st.tabs(['Fidelity', 'Schwab'])
with tabs[0]:
    holdings_csv = st.file_uploader('Upload CSV', type=['csv'])
    if holdings_csv:
        holdings_f = StringIO(holdings_csv.getvalue().decode('utf-8'))
        holdings_df = parse_fidelity(holdings_f)

if holdings_df is not None and not holdings_df.empty:
#    st.dataframe(holdings_df)
    all_tickers = list(holdings_df[holdings_df['security_type'] == 'Security']['ticker'].unique())
    # tickers = st.multiselect('Tickers to Query', all_tickers, default=all_tickers)
    # query_yf = st.button('Query Yahoo Finance')
    # if query_yf:
    try:
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

    st.metric('Current Value', f'${holdings_df["current_value"].sum():,.0f}')

    # Plot equities using Plotly
    import plotly.express as px
    agg_df = holdings_df[holdings_df['security_type'] == 'Security'][['ticker', 'quantity', 'cost_basis', 'current_value']].groupby('ticker').sum().sort_values(by='current_value').reset_index()
    fig = px.bar(agg_df, x='ticker', y='current_value', text_auto='.2s', title='Tickers')
    fig.update_layout(yaxis=dict(tickformat='$,d', fixedrange=True))
    fig.update_xaxes(fixedrange=True)
    st.plotly_chart(fig, use_container_width=True)

    non_equities_cols = st.columns(4)
    non_equities_cols[0].metric('CDs', f'${holdings_df[holdings_df["security_type"] == "CD"]["current_value"].sum():,.0f}')
    non_equities_cols[1].metric('Treasuries', f'${holdings_df[holdings_df["security_type"] == "Treasury"]["current_value"].sum():,.0f}')
    non_equities_cols[2].metric('Money Market', f'${holdings_df[holdings_df["security_type"] == "Money Market"]["current_value"].sum():,.0f}')
    non_equities_cols[3].metric('Cash', f'${holdings_df[holdings_df["security_type"] == "Cash"]["current_value"].sum():,.0f}')

    st.download_button(
        'Download aggregated holdings as CSV',
        data=holdings_df[['ticker', 'quantity', 'cost_basis']].groupby('ticker').sum().reset_index().to_csv(index=False),
        file_name='portfolio.csv',
    )
