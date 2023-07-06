import yfinance as yf


def download_ticker_data(tickers, period='1d'):
    # Special case tickers for yfinance lookup
    tickers = set(tickers)
    if 'BRKB' in tickers:
        tickers.remove('BRKB')
        tickers.add('BRK-B')
    ticker_df = yf.download(tickers=tickers, period=period, group_by='ticker')
    ticker_df = ticker_df.stack(level=0).reset_index(names=['date', 'ticker'])
    max_dates = ticker_df.groupby('ticker')['date'].idxmax()
    ticker_df = ticker_df.loc[max_dates]
    ticker_df.rename(
        columns={'Adj Close': 'adj_close', 'Close': 'close', 'High': 'high', 'Low': 'low', 'Open': 'open', 'Volume': 'volume'},
        inplace=True,
    )
    ticker_df['ticker'] = ticker_df['ticker'].str.replace('BRK-B', 'BRKB')
    return ticker_df
