import re
from typing import Any

import numpy as np
import pandas as pd


def _column(df: pd.DataFrame, hint: str, preferred: list[str] | None = None) -> str | None:
    names = list(map(str, df.columns))
    lowered = hint.lower()
    for name in sorted(names, key=len, reverse=True):
        plural = name.lower()[:-1] + "ies" if name.lower().endswith("y") else name.lower() + "s"
        if name.lower() in lowered or plural in lowered:
            return name
    if preferred:
        for p in preferred:
            for name in names:
                if p in name.lower():
                    return name
    tokens = [t for t in re.findall(r"[a-z0-9_]+", hint.lower()) if len(t) > 2]
    for token in tokens:
        for name in names:
            if token in name.lower():
                return name
    return None


def analyze(df: pd.DataFrame, question: str, previous: dict | None = None) -> dict[str, Any]:
    q = question.lower()
    numeric = [str(c) for c in df.select_dtypes(include="number").columns]
    cat = [str(c) for c in df.select_dtypes(exclude="number").columns]
    metric = (
        _column(
            df[numeric], q, ["revenue", "sales", "profit", "amount", "price", "quantity", "units"]
        )
        if numeric
        else None
    )
    if metric not in numeric:
        metric = numeric[0] if numeric else None
    group = _column(df[cat], q) if cat else None
    chart = any(w in q for w in ["plot", "chart", "graph", "visualize", "show"])
    data: list[dict] = []
    viz = None
    result: Any
    code = None
    kind = "summary"

    if previous and previous.get("analysis_type") == "time_series" and "declin" in q:
        rows = previous.get("result", [])
        negative = [r for r in rows if r.get("change_pct") is not None and r["change_pct"] < 0]
        date_col = next(
            (str(c) for c in df if "date" in str(c).lower() or "time" in str(c).lower()), None
        )
        metric = next((c for c in numeric if c in str(previous.get("code", ""))), metric)
        dimension = next(
            (
                str(c)
                for c in df.select_dtypes(exclude="number").columns
                if "region" in str(c).lower()
            ),
            None,
        )
        if negative and date_col and metric and dimension:
            current = negative[0]["period"]
            prior_month = (pd.Period(current, freq="M") - 1).strftime("%Y-%m")
            dates = pd.to_datetime(df[date_col], errors="coerce").dt.strftime("%Y-%m")
            grouped = (
                df.assign(_period=dates)
                .groupby(["_period", dimension])[metric]
                .sum()
                .unstack(fill_value=0)
            )
            if current in grouped.index and prior_month in grouped.index:
                deltas = (grouped.loc[current] - grouped.loc[prior_month]).sort_values()
                result = [{"label": str(k), "value": round(float(v), 2)} for k, v in deltas.items()]
                answer = f"{dimension.title()} contribution to the decline from {prior_month} to {current}, measured as the change in {metric}. {deltas.index[0]} had the largest decrease ({deltas.iloc[0]:,.2f})."
                return {
                    "answer": answer,
                    "summary": answer,
                    "analysis_type": "follow_up",
                    "code": f"group {metric} by {dimension} for {prior_month} and {current}; subtract prior from current",
                    "result": result,
                    "visualization": {
                        "type": "bar",
                        "title": f"{metric} change by {dimension}",
                        "x": "label",
                        "y": "value",
                        "data": result,
                    },
                    "insights": [],
                    "warnings": [],
                    "confidence": "high",
                }
    if (
        previous
        and isinstance(previous.get("result"), list)
        and any(x in q for x in ["plot it", "chart it", "show that as a chart", "visualize that"])
    ):
        prior_rows = previous["result"]
        if prior_rows and isinstance(prior_rows[0], dict):
            keys = list(prior_rows[0])
            xkey = "label" if "label" in keys else "period" if "period" in keys else keys[0]
            ykey = (
                "value"
                if "value" in keys
                else next(
                    (k for k in keys if k != xkey and isinstance(prior_rows[0][k], (int, float))),
                    None,
                )
            )
            if ykey:
                viz = {
                    "type": "bar" if xkey == "label" else "line",
                    "title": "Previous analysis",
                    "x": xkey,
                    "y": ykey,
                    "data": prior_rows,
                }
                answer = "Here is the previous analysis as a chart."
                return {
                    "answer": answer,
                    "summary": answer,
                    "analysis_type": "follow_up",
                    "code": None,
                    "result": prior_rows,
                    "visualization": viz,
                    "insights": [],
                    "warnings": [],
                    "confidence": "high",
                }

    if "correlat" in q:
        corr = df[numeric].corr(numeric_only=True).round(4).astype(object)
        corr = corr.where(pd.notna(corr), None)
        result = corr.reset_index().rename(columns={"index": "column"}).to_dict(orient="records")
        kind = "correlation"
        answer = f"Correlation matrix computed for {len(numeric)} numeric columns. Correlation describes association, not causation."
        code = "df.select_dtypes(include='number').corr()"
        if len(numeric) >= 2:
            vals = (
                corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
                .stack()
                .sort_values(key=abs, ascending=False)
            )
            if len(vals):
                answer += f" The strongest pair is {vals.index[0][0]} and {vals.index[0][1]} (r={vals.iloc[0]:.2f})."
    elif any(w in q for w in ["month", "monthly", "over time", "by date", "trend"]) and metric:
        date_col = next(
            (str(c) for c in df if "date" in str(c).lower() or "time" in str(c).lower()), None
        )
        if not date_col:
            raise ValueError("A date/time column is required for a time-series analysis.")
        ts = df[[date_col, metric]].copy()
        ts[date_col] = pd.to_datetime(ts[date_col], errors="coerce")
        operation = "mean" if "average" in q or "mean" in q else "sum"
        ts = (
            ts.dropna()
            .sort_values(date_col)
            .set_index(date_col)[metric]
            .resample("MS")
            .agg(operation)
            .dropna()
        )
        change = ts.pct_change() * 100
        result = [
            {
                "period": idx.strftime("%Y-%m"),
                metric: round(float(val), 2),
                "change_pct": round(float(change.loc[idx]), 2)
                if pd.notna(change.loc[idx])
                else None,
            }
            for idx, val in ts.items()
        ]
        answer = f"Monthly {metric} {'averages' if operation == 'mean' else 'totals'} for {len(result)} periods."
        if len(ts) > 1:
            first, last = float(ts.iloc[0]), float(ts.iloc[-1])
            delta = (last / first - 1) * 100 if first else 0
            answer += f" The change from the first to last observed month is {delta:+.1f}%."
        if "best" in q or "highest" in q:
            best = ts.idxmax()
            answer += f" The highest month was {best:%B %Y} at {float(ts.max()):,.2f}."
        kind = "time_series"
        code = f"df.assign(date=pd.to_datetime(df[{date_col!r}])).groupby(pd.Grouper(key='date', freq='MS'))[{metric!r}].{operation}()"
        viz = {
            "type": "line",
            "title": f"Monthly {metric}",
            "x": "period",
            "y": metric,
            "data": result,
        }
        if "moving average" in q:
            values = ts.rolling(3).mean()
            result = [
                {
                    **r,
                    "moving_average_3": round(float(values.iloc[i]), 2)
                    if pd.notna(values.iloc[i])
                    else None,
                }
                for i, r in enumerate(result)
            ]
            answer = "Monthly totals with a 3-period moving average."
    elif "anomal" in q or "unusual" in q:
        col = _column(df, q, ["revenue", "sales", "profit", "amount", "price"])
        if col not in numeric:
            col = numeric[0] if numeric else None
        if not col:
            raise ValueError("Anomaly detection requires a numeric column.")
        series = df[col].dropna()
        q1, q3 = series.quantile([0.25, 0.75])
        spread = q3 - q1
        low, high = q1 - 1.5 * spread, q3 + 1.5 * spread
        odd = df.loc[(df[col] < low) | (df[col] > high), [col]].head(100)
        result = {
            "method": "IQR",
            "lower_bound": _num(low),
            "upper_bound": _num(high),
            "count": int(((df[col] < low) | (df[col] > high)).sum()),
            "observations": odd.to_dict(orient="records"),
        }
        answer = f"IQR screening identified {result['count']} statistically unusual {col} observation(s). This method flags outliers; it does not label them as errors or fraud."
        kind = "anomaly_detection"
        code = f"q1,q3=df[{col!r}].quantile([.25,.75]); iqr=q3-q1\n(df[{col!r}]<q1-1.5*iqr)|(df[{col!r}]>q3+1.5*iqr)"
    elif (
        "median" in q
        or "mode" in q
        or "standard deviation" in q
        or "variance" in q
        or "quantile" in q
    ):
        if not metric:
            raise ValueError("No numeric column is available for this statistic.")
        series = df[metric].dropna()
        stat = (
            "median"
            if "median" in q
            else "mode"
            if "mode" in q
            else "std"
            if "standard deviation" in q
            else "variance"
            if "variance" in q
            else "quantiles"
        )
        vals = (
            series.quantile([0.25, 0.5, 0.75]).to_dict()
            if stat == "quantiles"
            else {
                stat: (
                    float(series.mode().iloc[0])
                    if stat == "mode" and not series.mode().empty
                    else getattr(series, stat)()
                    if stat != "mode"
                    else None
                )
            }
        )
        result = {k: round(float(v), 4) for k, v in vals.items()}
        answer = f"Computed {stat} for {metric}: {result}."
        kind = "statistic"
        code = f"df[{metric!r}].{stat if stat != 'quantiles' else 'quantile([.25,.5,.75])'}()"
    elif any(w in q for w in ["missing", "null", "empty value"]):
        result = [
            {
                "column": c,
                "missing": int(df[c].isna().sum()),
                "percent": round(float(df[c].isna().mean() * 100), 2),
            }
            for c in df
            if df[c].isna().any()
        ]
        kind = "missing_values"
        answer = (
            "No missing values were found."
            if not result
            else f"Found missing values in {len(result)} column(s)."
        )
        code = "df.isna().sum()"
    elif "how many rows" in q or "row count" in q or "number of rows" in q:
        result = {"rows": len(df), "columns": len(df.columns)}
        answer = f"The dataset has {len(df):,} rows and {len(df.columns)} columns."
        code = "df.shape"
    elif "forecast" in q:
        date_col = next(
            (str(c) for c in df if "date" in str(c).lower() or "time" in str(c).lower()), None
        )
        if not date_col or not metric:
            raise ValueError("Forecasting needs a date/time column and a numeric metric.")
        ts = df[[date_col, metric]].copy()
        ts[date_col] = pd.to_datetime(ts[date_col], errors="coerce")
        ts = (
            ts.dropna()
            .sort_values(date_col)
            .set_index(date_col)[metric]
            .resample("MS")
            .sum()
            .dropna()
        )
        if len(ts) < 3:
            raise ValueError("At least three time periods are required for a baseline forecast.")
        delta = float(ts.diff().tail(3).mean()) if len(ts) > 1 else 0
        future = [
            {
                "period": (ts.index[-1] + pd.offsets.MonthBegin(i + 1)).isoformat(),
                "actual": None,
                "value": round(float(max(0, ts.iloc[-1] + delta * (i + 1))), 2),
            }
            for i in range(3)
        ]
        history = [
            {"period": i.isoformat(), "actual": round(float(v), 2), "value": round(float(v), 2)}
            for i, v in ts.items()
        ]
        result = {"history": history, "forecast": future}
        answer = "This is a simple linear-drift baseline forecast; treat future values as estimates, not guaranteed outcomes."
        kind = "forecast"
        code = "monthly = df.set_index(date).resample('MS')[metric].sum()\nforecast = last_value + mean_recent_change * horizon"
        viz = {
            "type": "line",
            "title": f"{metric} forecast (baseline)",
            "x": "period",
            "y": "value",
            "data": history + future,
        }
    elif "average" in q or "mean" in q:
        if not metric:
            raise ValueError("No numeric column is available to calculate an average.")
        if group and group in cat:
            agg = (
                df.groupby(group, dropna=False)[metric].mean().sort_values(ascending=False).round(2)
            )
            data = [{"label": str(k), "value": _num(v)} for k, v in agg.items()]
            answer = f"Average {metric} by {group}, ranked from highest to lowest."
            kind = "aggregation"
            code = f"df.groupby({group!r})[{metric!r}].mean().sort_values(ascending=False)"
            result = data
        else:
            value = float(df[metric].mean())
            result = {"column": metric, "average": round(value, 4)}
            answer = f"The average {metric} is {value:,.2f}."
            kind = "statistic"
            code = f"df[{metric!r}].mean()"
    elif group and (
        "top" in q
        or "most" in q
        or "highest" in q
        or "by " in q
        or "compare" in q
        or "between" in q
        or "across" in q
        or chart
    ):
        if not metric:
            raise ValueError("No numeric metric column could be identified.")
        agg = df.groupby(group, dropna=False)[metric].sum().sort_values(ascending=False)
        m = re.search(r"top\s+(\d+)", q)
        limit = min(int(m.group(1)), 50) if m else 10
        agg = agg.head(limit).round(2)
        result = [{"label": str(k), "value": _num(v)} for k, v in agg.items()]
        answer = (
            f"Comparison of total {metric} across {group}."
            if any(w in q for w in ["compare", "between", "across"])
            else f"Top {len(result)} {group} values by total {metric}."
        )
        kind = "aggregation"
        code = f"df.groupby({group!r})[{metric!r}].sum().sort_values(ascending=False).head({limit})"
    else:
        result = {
            "rows": len(df),
            "columns": len(df.columns),
            "numeric_columns": numeric,
            "categorical_columns": cat,
        }
        answer = f"This dataset has {len(df):,} rows. Ask about a statistic, missing values, correlations, grouped totals, or a forecast."
        kind = "dataset_summary"

    if (
        (chart or kind == "aggregation")
        and isinstance(result, list)
        and result
        and isinstance(result[0], dict)
        and "label" in result[0]
    ):
        viz = {
            "type": "bar",
            "title": f"{metric} by {group}",
            "x": "label",
            "y": "value",
            "data": result,
        }
    insight = [answer] if kind == "aggregation" and result else []
    return {
        "answer": answer,
        "summary": answer,
        "analysis_type": kind,
        "code": code,
        "result": result,
        "visualization": viz,
        "insights": insight,
        "warnings": [],
        "confidence": "high",
    }


def _num(v):
    return float(v) if np.isfinite(v) else None
