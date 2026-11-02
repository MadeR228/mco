"""Перетворення результатів NumPy/pandas у JSON-сумісні значення."""
import math

import numpy as np
import pandas as pd


def clean(obj):
    """Рекурсивно: numpy → Python, NaN/±∞ → None (JSON не має нескінченностей)."""
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return clean(obj.tolist())
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        f = float(obj)
        return f if math.isfinite(f) else None
    return obj


def frame_to_table(df: pd.DataFrame) -> dict:
    """Таблиця альтернатив у форматі API: стовпці, числові стовпці, записи."""
    df = df.dropna(how='all').reset_index(drop=True)
    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    text = [c for c in df.columns if c not in numeric]
    records = [{str(k): clean(v) for k, v in row.items()} for row in df.to_dict(orient='records')]
    return {'columns': [str(c) for c in df.columns], 'numeric_columns': [str(c) for c in numeric],
            'name_column': str(text[0]) if text else None, 'rows': len(df), 'records': records}


def parse_inf(v):
    """«inf», «∞», «Infinity» → math.inf; решта – як є."""
    if isinstance(v, str) and v.strip().lower() in ('inf', '∞', 'infinity', '+inf'):
        return math.inf
    return v
