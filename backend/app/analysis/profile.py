import json
from typing import Any

import numpy as np
import pandas as pd


def _clean(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    return value.item() if hasattr(value, "item") else value


def profile_dataframe(df: pd.DataFrame) -> dict:
    if df.empty or len(df.columns) == 0:
        raise ValueError("The dataset contains no rows or columns.")
    cols = []
    for name in df.columns:
        s = df[name]
        semantic = "numeric" if pd.api.types.is_numeric_dtype(s) else "categorical"
        parsed = (
            pd.to_datetime(s, errors="coerce", format="mixed")
            if semantic == "categorical"
            else None
        )
        if parsed is not None and parsed.notna().mean() >= 0.8:
            semantic = "datetime"
        elif pd.api.types.is_bool_dtype(s):
            semantic = "boolean"
        elif s.nunique(dropna=True) > 0 and s.nunique(dropna=True) >= len(s.dropna()) * 0.9:
            semantic = "identifier"
        item = {
            "name": str(name),
            "dtype": str(s.dtype),
            "semantic_type": semantic,
            "null_count": int(s.isna().sum()),
            "null_percentage": round(float(s.isna().mean() * 100), 2),
            "unique_count": int(s.nunique(dropna=True)),
            "examples": [_clean(x) for x in s.dropna().head(5).tolist()],
        }
        if semantic == "numeric":
            item.update(
                {
                    k: (round(float(v), 4) if pd.notna(v) else None)
                    for k, v in {
                        "min": s.min(),
                        "max": s.max(),
                        "mean": s.mean(),
                        "median": s.median(),
                        "std": s.std(),
                        "q25": s.quantile(0.25),
                        "q75": s.quantile(0.75),
                    }.items()
                }
            )
        cols.append(item)
    mem = int(df.memory_usage(deep=True).sum())
    return {
        "row_count": len(df),
        "column_count": len(df.columns),
        "duplicate_rows": int(df.duplicated().sum()),
        "memory_bytes": mem,
        "missing_cells": int(df.isna().sum().sum()),
        "columns": cols,
        "preview": json.loads(df.head(10).to_json(orient="records", date_format="iso")),
    }
