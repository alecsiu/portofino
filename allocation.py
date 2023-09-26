import math

from typing import List, Tuple

import pandas as pd


class AssetClass:

    def __init__(self, name):
        self.name = name
        self.children = {}  # ordered dict
        self.parent = None

    def __getitem__(self, key):
        return self.children[key]
    
    def __lshift__(self, other):
        self.children[other.name] = other
        other.parent = self
        return self
    
    def __rshift__(self, other):
        return self.children[other]
    
    def __str__(self) -> str:
        s = self.name
        if self.children:
            s += f' → [{" + ".join(str(c) for c in self.children.values())}]'
        return s
    
    def path(self):
        s = self.name
        parent = self.parent
        while parent:
            s = f'{parent.name} → {s}'
            parent = parent.parent
        return s
    
    def hierarchy(self):
        h = []
        parent = self.parent
        while parent:
            h.append(parent.name)
            parent = parent.parent
        h.reverse()
        return h

    def search(self, name):
        if self.name == name:
            return self        
        if not self.children:
            return None
        for child in self.children.values():
            found_node = child.search(name)
            if found_node:
                return found_node
        return None


class Allocation(AssetClass):
    
    def __init__(self, name, weight):
        super().__init__(name)
        self.weight = weight

    def __str__(self) -> str:
        s = f'{self.name} x {self.weight}'
        if self.children:
            s += f' → [{" + ".join(str(c) for c in self.children.values())}]'
        return s
    
    def validate_weights(self):
        if not self.children:
            return []
        errors = []
        total_alloc = sum(child.weight for child in self.children.values())
        if not math.isclose(total_alloc, 1):
            errors.append(f'{self.name} allocation must equal 1.0, {" + ".join(child.name + " x " + str(child.weight) for child in self.children.values())} == {total_alloc:.4f}, error == {1.0 - total_alloc:.4f}')
        for child in self.children.values():
            errors.extend(child.validate_weights())
        return errors

    def collect_weights(self, max_depth, current_depth):
        if not self.children or current_depth == max_depth:
            return [(self.name, self.weight)]
        weights = []
        for child in self.children.values():
            weights.extend([(ticker, self.weight * weight) for ticker, weight in child.collect_weights(max_depth, current_depth + 1)])
        return weights
    
    def get_ticker_weights(self):
        return [(ticker, weight) for ticker, weight in self.collect_weights(2, 0)]
    
    def get_asset_class_weights(self):
        return [(asset_class, weight) for asset_class, weight in self.collect_weights(1, 0)]
        
    def collect_leaves(self):
        if not self.children:
            return [self]
        leaves = []
        for child in self.children.values():
            leaves.extend(child.collect_leaves())
        return leaves
    
    def to_df(self):
        weights = {w[0]: w[1] for w in self.collect_weights(2, 0)}
        return pd.DataFrame(
            [(leaf.parent.name, leaf.name, weights[leaf.name]) for leaf in self.collect_leaves()],
            columns=['category', 'ticker', 'weight'],
        )


asset_classes = AssetClass('Global')
asset_classes << AssetClass('US Equities')
asset_classes << AssetClass('Intl Equities')
asset_classes << AssetClass('EM Equities')
asset_classes << AssetClass('US Bonds')
asset_classes << AssetClass('Short-Term')
asset_classes << AssetClass('US Real Estate')
asset_classes << AssetClass('Alternatives')

mapping = {
    'US Equities': [
        'FXAIX', 'ITOT', 'AVUV', 'QQQM', 'QQQJ', 'COWZ', 'SCHD', 'OMFL',
        'AAPL', 'ABNB', 'ADBE', 'AMZN', 'AMD', 'BRKB', 'CELH',
        'CRM', 'GOOG', 'GOOGL', 'KVUE', 'META', 'MNST', 'MSFT',
        'NET', 'NVDA', 'RXRX', 'SOXX', 'TEAM', 'TSLA', 'TTD'
    ],
    'Intl Equities': [
        'VEA', 'DXJ', 'HEFA', 'AVDV', 'DFIV',
        'ASML', 'SHOP', 'NVO', 'TSM'
    ],
    'EM Equities': [
        'SPEM', 'AVES', 'XCEM',
    ],
    'US Bonds': [
        'PFXF', 'VTEB', 'VWIUX', 'VWALX', 'BND', 'FBND', 'JAAA', 'ICLO', 'CD', 'Treasury'
    ],
    'Short-Term': [
        'TFLO', 'FLOT', 'JMST', 'TBIL', 'Money Market', 'VMSXX'
    ],
    'US Real Estate': [
        'VGSLX', 'AVRE'
    ],
    'Alternatives': [
        'CTA', 'DBMF', 'KMLM',
    ],
}

for asset_class, tickers in mapping.items():
    for ticker in tickers:
        asset_classes >> asset_class << AssetClass(ticker)

single_stocks = {
    'AAPL', 'ABNB', 'ADBE', 'AMZN', 'AMD', 'BRKB', 'CELH',
    'CRM', 'GOOG', 'GOOGL', 'KVUE', 'META', 'MNST', 'MSFT',
    'NET', 'NVDA', 'QABSY', 'RXRX', 'SOXX', 'TEAM', 'TSLA', 'TTD',
    'ASML', 'SHOP', 'NVO', 'TSM'
}


def create_global_allocation():
    global_allocation = Allocation('Global', 1.0)
    global_allocation << Allocation('US Equities', 0.42)
    global_allocation << Allocation('Intl Equities', 0.21)
    global_allocation << Allocation('US Bonds', 0.2)
    global_allocation << Allocation('EM Equities', 0.06)
    global_allocation << Allocation('US Real Estate', 0.05)
    global_allocation << Allocation('Short-Term', 0.06)
    
    global_allocation >> 'US Equities' << Allocation('ITOT', 0.44)
    global_allocation >> 'US Equities' << Allocation('AVUV', 0.18)
    global_allocation >> 'US Equities' << Allocation('QQQM', 0.18)
    global_allocation >> 'US Equities' << Allocation('COWZ', 0.08)
    global_allocation >> 'US Equities' << Allocation('SCHD', 0.04)
    global_allocation >> 'US Equities' << Allocation('OMFL', 0.08)
    global_allocation >> 'US Equities' << Allocation('QQQJ', 0)
        
    global_allocation >> 'Intl Equities' << Allocation('VEA', 0.45)
    global_allocation >> 'Intl Equities' << Allocation('DXJ', 0.05)
    global_allocation >> 'Intl Equities' << Allocation('HEFA', 0.1)
    global_allocation >> 'Intl Equities' << Allocation('AVDV', 0.20)
    global_allocation >> 'Intl Equities' << Allocation('DFIV', 0.20)

    global_allocation >> 'EM Equities' << Allocation('SPEM', 0.4)
    global_allocation >> 'EM Equities' << Allocation('AVES', 0.4)
    global_allocation >> 'EM Equities' << Allocation('XCEM', 0.2)

    global_allocation >> 'US Bonds' << Allocation('VTEB', 0.42)
    global_allocation >> 'US Bonds' << Allocation('VWIUX', 0.22)
    global_allocation >> 'US Bonds' << Allocation('VWALX', 0.11)
    global_allocation >> 'US Bonds' << Allocation('JAAA', 0.01)
    global_allocation >> 'US Bonds' << Allocation('ICLO', 0.01)
    global_allocation >> 'US Bonds' << Allocation('Treasury', 0.13)
    global_allocation >> 'US Bonds' << Allocation('CD', 0.1)

    global_allocation >> 'Short-Term' << Allocation('TFLO', 0.5)
    global_allocation >> 'Short-Term' << Allocation('FLOT', 0.25)
    global_allocation >> 'Short-Term' << Allocation('JMST', 0.25)  
    global_allocation >> 'Short-Term' << Allocation('TBIL', 0)
    global_allocation >> 'Short-Term' << Allocation('Money Market', 0)

    global_allocation >> 'US Real Estate' << Allocation('VGSLX', 0.5)
    global_allocation >> 'US Real Estate' << Allocation('AVRE', 0.5)

    return global_allocation


def analyze_allocation(
        holdings_df, key: str, key_weights: List[Tuple[str, float]], cash_to_invest: float = 0.0
    ):
    result_df = holdings_df[[key, 'current_value']].groupby([key]).sum()
    investable = result_df['current_value'].sum() + cash_to_invest
    result_df['current_alloc'] = result_df['current_value'] / investable
    alloc_sum = sum(percent for _, percent in key_weights)
    if not math.isclose(alloc_sum, 1):
        raise ValueError(f'Allocations must sum to 1.0, current allocation = {alloc_sum}')
    desired_allocation_df = pd.DataFrame.from_records([
        {key: category, 'target_alloc': allocation} for category, allocation in key_weights
    ]).set_index(key)
    result_df = result_df.merge(desired_allocation_df, how='outer', on=key).fillna(0)
    result_df['target_pct'] = result_df['target_alloc'] * 100.0
    result_df['drift'] = result_df['current_alloc'] - result_df['target_alloc']
    result_df['drift_value'] = result_df['current_value'] - (result_df['target_alloc'] * investable)
    result_df['target_value'] = result_df['current_value'] - result_df['drift_value']
    result_df['action'] = result_df['drift_value'].apply(lambda dv: '🟢 Buy' if dv < 0 else '🔴 Sell' if dv > 0 else '⏸️ Hold')
    return result_df
