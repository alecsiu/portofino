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
    
    def collect_weights(self):
        if not self.children:
            return [(self.name, self.weight)]
        weights = []
        for child in self.children.values():
            weights.extend([(ticker, self.weight * weight) for ticker, weight in child.collect_weights()])
        return weights
    
    def collect_leaves(self):
        if not self.children:
            return [self]
        leaves = []
        for child in self.children.values():
            leaves.extend(child.collect_leaves())
        return leaves
    
    def to_df(self):
        weights = {w[0]: w[1] for w in self.collect_weights()}
        return pd.DataFrame([(leaf.parent.name, leaf.name, weights[leaf.name]) for leaf in self.collect_leaves()], columns=['category', 'ticker', 'weight'])
        

def create_global_allocation():
    global_allocation = Allocation('Global', 1.0)
    global_allocation << Allocation('US Equities', 0.42)
    global_allocation << Allocation('Intl Equities', 0.21)
    global_allocation << Allocation('US Bonds', 0.25)
    global_allocation << Allocation('EM Equities', 0.07)
    global_allocation << Allocation('US Real Estate', 0.05)

    global_allocation >> 'US Equities' << Allocation('ITOT', 0.46)
    global_allocation >> 'US Equities' << Allocation('AVUV', 0.18)
    global_allocation >> 'US Equities' << Allocation('AVLV', 0.06)
    global_allocation >> 'US Equities' << Allocation('QQQM', 0.18)
    global_allocation >> 'US Equities' << Allocation('DUHP', 0.06)
    global_allocation >> 'US Equities' << Allocation('COWZ', 0.06)
    
    global_allocation >> 'Intl Equities' << Allocation('VEA', 0.60)
    global_allocation >> 'Intl Equities' << Allocation('AVDV', 0.20)
    global_allocation >> 'Intl Equities' << Allocation('DFIV', 0.20)

    global_allocation >> 'EM Equities' << Allocation('VWO', 0.4)
    global_allocation >> 'EM Equities' << Allocation('AVES', 0.6)

    global_allocation >> 'US Bonds' << Allocation('VTEB', 0.20)
    global_allocation >> 'US Bonds' << Allocation('VWALX', 0.20)
    global_allocation >> 'US Bonds' << Allocation('VMSXX', 0.20)
    global_allocation >> 'US Bonds' << Allocation('TBIL', 0.30)
    global_allocation >> 'US Bonds' << Allocation('CD / Treasury', 0.10)

    global_allocation >> 'US Real Estate' << Allocation('VGSLX', 0.5)
    global_allocation >> 'US Real Estate' << Allocation('AVRE', 0.5)

    return global_allocation


def analyze_allocation(
        holdings_df, key: str, allocations: List[Tuple[str, float]], cash_to_invest: float = 0.0
    ):
    result_df = holdings_df[[key, 'current_value']].groupby([key]).sum()
    investable = result_df['current_value'].sum() + cash_to_invest
    result_df['current_alloc'] = result_df['current_value'] / investable
    alloc_sum = sum(percent for _, percent in allocations)
    if not math.isclose(alloc_sum, 1):
        raise ValueError(f'Allocations must sum to 1.0, current allocation = {alloc_sum}')
    desired_allocation_df = pd.DataFrame.from_records([
        {key: category, 'target_alloc': allocation} for category, allocation in allocations
    ]).set_index(key)
    result_df = result_df.merge(desired_allocation_df, how='outer', on=key).fillna(0)
    result_df['target_pct'] = result_df['target_alloc'] * 100.0
    result_df['drift'] = result_df['current_alloc'] - result_df['target_alloc']
    result_df['drift_value'] = result_df['current_value'] - (result_df['target_alloc'] * investable)
    result_df['target_value'] = result_df['current_value'] - result_df['drift_value']
    result_df['action'] = result_df['drift_value'].apply(lambda dv: '🟢 Buy' if dv < 0 else '🔴 Sell' if dv > 0 else '⏸️ Hold')
    return result_df
