import re
import pandas as pd

from datetime import datetime


def parse_fidelity(f):
    holdings_df = pd.read_csv(f).head(-3)  # exclude trailer

    # Filter pending activity and BrokerageLink entries (dupes)
    holdings_df = holdings_df[
        (holdings_df.Symbol != 'Pending Activity') & \
        (holdings_df.Description != 'BROKERAGELINK')
    ].copy()

    # Fix up legacy column names
    if 'Cost Basis Total' in holdings_df.columns:
        holdings_df.rename(
            columns={
                'Cost Basis Total': 'Cost Basis',
                'Average Cost Basis': 'Cost Basis Per Share'
            },
            inplace=True,
        )

    # Normalize column names
    holdings_df.rename(
        columns={
            'Account Number': 'account_number',
            'Account Name': 'account_name',
            'Symbol': 'ticker',
            'Quantity': 'quantity',            
            'Cost Basis': 'cost_basis',
            'Cost Basis Per Share': 'cost_basis_per_share',
            'Description': 'description',
        },
        inplace=True,
    )

    # Convert $ values into floats
    try:
        for col in ['cost_basis', 'cost_basis_per_share']:
            holdings_df[col] = holdings_df[col].apply(lambda v: float(str(v).replace('$', '') if v != '--' else 0))
    except Exception:
        print('Error parsing csv')
        raise

    # Remove any '**' suffix from tickers
    holdings_df['ticker'] = holdings_df['ticker'].apply(lambda t: t.replace('**', ''))

    # Identify security types
    def _infer_security_type(description):
        if description.startswith('UNITED STATES TREAS'):
            return 'Treasury'
        elif 'MONEY MARKET' in description:
            return 'Money Market'
        elif description.startswith('FDIC-INSURED DEPOSIT SWEEP'):
            return 'Cash'
        elif re.search(r'CD \d\.\d+%', description) is not None:
            return 'CD'
        else:
            return 'Security'
        
    holdings_df['security_type'] = holdings_df['description'].apply(_infer_security_type)

    # Parse interest rates from CDs
    holdings_df['yield'] = holdings_df['description'].apply(
        lambda d: float(re.search(r'\d\.\d+%', d).group(0).replace('%', '')) if re.search(r'CD \d\.\d+%', d) is not None else None
    )

    # Parse maturity dates from CDs and Treasuries
    def _parse_maturity_date(row):
        if row['security_type'] not in ('Treasury', 'CD'):
            return None
        tokens = row['description'].split()
        try:
            maturity_date = datetime.strptime(tokens[-1], '%m/%d/%Y')
        except:
            maturity_date = None
        return maturity_date

    holdings_df['maturity_date'] = holdings_df.apply(_parse_maturity_date, axis=1)

    # Only keep relevant columns
    holdings_df = holdings_df[[
        'account_number',
        'account_name',
        'ticker',
        'quantity',
        'cost_basis',
        'cost_basis_per_share',
        'description',
        'security_type',
        'yield',
        'maturity_date',
    ]]

    # Hard coded stuff
    holdings_df['firm'] = 'Fidelity'

    return holdings_df


def parse_schwab(f):
    holdings_df = pd.read_csv(f).head(-1)  # exclude trailer

