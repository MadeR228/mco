"""Жорсткі обмеження на альтернативи (фільтри за значеннями атрибутів)."""
from dataclasses import dataclass

import numpy as np
import pandas as pd

OPERATORS = ('≤', '≥', '<', '>', '=', '≠', 'у списку', 'не у списку', 'містить')


@dataclass
class Constraint:
    column: str
    op: str
    value: object

    def describe(self):
        return f'{self.column} {self.op} {self.value}'


def _as_list(value):
    return [v.strip() for v in str(value).split(',') if v.strip()]


def constraint_mask(df: pd.DataFrame, c: Constraint) -> np.ndarray:
    if c.column not in df.columns:
        raise ValueError(f'Обмеження посилається на відсутній стовпець «{c.column}»')
    col = df[c.column]
    if c.op in ('≤', '≥', '<', '>', '=', '≠') and pd.api.types.is_numeric_dtype(col):
        try:
            v = float(str(c.value).replace(',', '.'))
        except ValueError:
            raise ValueError(f'Значення обмеження «{c.describe()}» має бути числом') from None
        x = col.to_numpy(dtype=float)
        return {'≤': x <= v, '≥': x >= v, '<': x < v, '>': x > v,
                '=': np.isclose(x, v), '≠': ~np.isclose(x, v)}[c.op]
    s = col.astype(str).str.strip()
    if c.op == '=':
        return (s == str(c.value).strip()).to_numpy()
    if c.op == '≠':
        return (s != str(c.value).strip()).to_numpy()
    if c.op == 'у списку':
        return s.isin(_as_list(c.value)).to_numpy()
    if c.op == 'не у списку':
        return (~s.isin(_as_list(c.value))).to_numpy()
    if c.op == 'містить':
        return s.str.contains(str(c.value), case=False, regex=False).to_numpy()
    raise ValueError(f'Оператор «{c.op}» не можна застосувати до текстового стовпця «{c.column}»')


def apply(df: pd.DataFrame, constraints):
    """Повертає (маска допустимих альтернатив, список причин виключення для кожного рядка)."""
    ok = np.ones(len(df), dtype=bool)
    reasons = [[] for _ in range(len(df))]
    for c in constraints:
        mask = constraint_mask(df, c)
        for i in np.where(~mask)[0]:
            reasons[i].append(c.describe())
        ok &= mask
    return ok, reasons
