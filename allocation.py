import math

from typing import List, Tuple

import pandas as pd


class Allocation:
    
    def __init__(self, name, weight):
        self.name = name
        self.weight = weight
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
        s = f'{self.name} x {self.weight}'
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
    
    def get_asset_class_mapping(self):
        return {leaf.name: leaf.parent.name for leaf in self.collect_leaves()}
    
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
        

def create_global_allocation():
    global_allocation = Allocation('Global', 1.0)
    global_allocation << Allocation('US Equities', 0.42)
    global_allocation << Allocation('Intl Equities', 0.21)
    global_allocation << Allocation('US Bonds', 0.21)
    global_allocation << Allocation('EM Equities', 0.06)
    global_allocation << Allocation('US Real Estate', 0.05)
    global_allocation << Allocation('Short-Term', 0.05)
    
    global_allocation >> 'US Equities' << Allocation('ITOT', 0.48)
    global_allocation >> 'US Equities' << Allocation('AVUV', 0.18)
    global_allocation >> 'US Equities' << Allocation('QQQM', 0.18)
    global_allocation >> 'US Equities' << Allocation('COWZ', 0.08)
    global_allocation >> 'US Equities' << Allocation('SCHD', 0.08)
    global_allocation >> 'US Equities' << Allocation('QQQJ', 0)
        
    global_allocation >> 'Intl Equities' << Allocation('VEA', 0.60)
    global_allocation >> 'Intl Equities' << Allocation('AVDV', 0.20)
    global_allocation >> 'Intl Equities' << Allocation('DFIV', 0.20)

    global_allocation >> 'EM Equities' << Allocation('SPEM', 0.4)
    global_allocation >> 'EM Equities' << Allocation('AVES', 0.4)
    global_allocation >> 'EM Equities' << Allocation('FRDM', 0.2)

    global_allocation >> 'US Bonds' << Allocation('VTEB', 0.22)
    global_allocation >> 'US Bonds' << Allocation('VWIUX', 0.22)
    global_allocation >> 'US Bonds' << Allocation('VWALX', 0.11)
    global_allocation >> 'US Bonds' << Allocation('IBDP', 0.05)  # 4-year corp bond ladder
    global_allocation >> 'US Bonds' << Allocation('IBDQ', 0.05)
    global_allocation >> 'US Bonds' << Allocation('IBDR', 0.05)
    global_allocation >> 'US Bonds' << Allocation('IBDS', 0.05)
    global_allocation >> 'US Bonds' << Allocation('Treasury', 0.25)

    global_allocation >> 'Short-Term' << Allocation('CD', 0.1)
    global_allocation >> 'Short-Term' << Allocation('TFLO', 0.6)
    global_allocation >> 'Short-Term' << Allocation('FLOT', 0.3)
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
