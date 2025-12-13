# backend/insights_engine.py
import math
import numpy as np
import pandas as pd


def top_bottom_groups(df, value_col, group_col, top_n=3):
    sorted_df = df.sort_values(by=value_col, ascending=False)
    top = sorted_df.head(top_n).to_dict(orient="records")
    bottom = sorted_df.tail(top_n).sort_values(by=value_col, ascending=True).to_dict(orient="records")
    return top, bottom

def detect_anomalies(series):
    if series.dtype.kind not in "fiu":
        return [], None, None
    mean = series.mean()
    std = series.std(ddof=0)
    if std == 0 or math.isnan(std):
        return [], mean, std
    z = (series - mean) / std
    anomalies = series[z.abs() > 2]
    return anomalies.index.tolist(), mean, std

def suggest_chart(df):
    cols = df.columns.tolist()

    if df.empty:
        return "table"

    if len(cols) == 1:
        return "kpi"

    if len(cols) == 2:
        # Categorical + numeric -> bar
        if df.iloc[:,0].dtype == object and np.issubdtype(df.iloc[:,1].dtype, np.number):
            return "bar"
        # Datetime + numeric -> line
        if np.issubdtype(df.iloc[:,0].dtype, np.datetime64) and np.issubdtype(df.iloc[:,1].dtype, np.number):
            return "line"

    return "table"

def summarize_grouped(df):
    group_col = df.columns[0]
    val_col = df.columns[1]

    # Ensure numeric values in metric column
    df[val_col] = pd.to_numeric(df[val_col], errors="coerce")
    df = df.dropna(subset=[val_col])

    if df.empty:
        return {
            "group_column": group_col,
            "value_column": val_col,
            "top": [],
            "bottom": [],
            "mean": None,
            "percent_difference_top_vs_median": None,
            "anomaly_count": 0,
            "bullets": ["No numeric values found for grouped analysis."]
        }

    sorted_df = df.sort_values(val_col, ascending=False)
    top = sorted_df.head(3).to_dict(orient="records")
    bottom = sorted_df.tail(3).sort_values(val_col, ascending=True).to_dict(orient="records")

    mean = float(df[val_col].mean())
    median = float(df[val_col].median())
    max_val = float(df[val_col].max())

    percent_diff = None
    if median != 0:
        percent_diff = ((max_val - median) / abs(median)) * 100

    # Anomaly detection using z-score
    std = df[val_col].std(ddof=0)
    if std == 0 or math.isnan(std):
        anomaly_count = 0
    else:
        zscores = (df[val_col] - mean) / std
        anomaly_count = int((zscores.abs() > 2).sum())

    bullets = []
    if top:
        bullets.append(f"Top groups: {', '.join([f'{x[group_col]} ({round(x[val_col],2)})' for x in top])}.")
    if bottom:
        bullets.append(f"Lowest groups: {', '.join([f'{x[group_col]} ({round(x[val_col],2)})' for x in bottom])}.")
    bullets.append(f"Average value across groups: {round(mean,2)}.")
    if percent_diff is not None:
        bullets.append(f"Top group is {round(percent_diff,1)}% above the median.")
    if anomaly_count > 0:
        bullets.append(f"Detected {anomaly_count} outlier groups.")

    return {
        "group_column": group_col,
        "value_column": val_col,
        "top": top,
        "bottom": bottom,
        "mean": mean,
        "percent_difference_top_vs_median": percent_diff,
        "anomaly_count": anomaly_count,
        "bullets": bullets
    }

def summarize_scalar(df):
    col = df.columns[0]
    try:
        val = float(df.iloc[0,0])
    except:
        val = df.iloc[0,0]
    bullets = [f"Value: {round(val,2) if isinstance(val,(int,float)) else val}"]
    return {"value_column": col, "value": val, "bullets": bullets}

def generate_insights_from_df(df: pd.DataFrame, sql: str, question: str):
    out = {"question": question, "generated_sql": sql, "insights": []}

    if df is None or df.empty:
        out["insights"] = ["Query returned no results."]
        out["suggested_chart"] = "table"
        return out

    # Convert date-like columns for chart detection
    # --- Safe date conversion: only try on object/string columns that look date-like ---
    for c in df.columns:
        try:
            # only consider object/string columns (avoid numeric)
            if df[c].dtype == object:
                sample_vals = df[c].dropna().astype(str).head(20).tolist()
                # quick heuristic: presence of common date separators or year-like tokens
                looks_like_date = any(
                    ("/" in s) or ("-" in s) or (":" in s) or (len(s) >= 8 and s[:4].isdigit())
                    for s in sample_vals
                )
                if looks_like_date:
                    # use coerce to avoid raising errors and to make dtype consistent
                    df[c] = pd.to_datetime(df[c], errors="coerce", infer_datetime_format=True)
        except Exception:
            # keep original column if parsing fails
            df[c] = df[c]


    # KPI case: single column
    if df.shape[1] == 1:
        summary = summarize_scalar(df)
        out["suggested_chart"] = "kpi"
        out["insights"] = summary["bullets"]
        out["details"] = summary
        return out

    # Try coerce second column to numeric for grouped analysis
    try:
        df.iloc[:,1] = pd.to_numeric(df.iloc[:,1], errors="coerce")
    except Exception:
        pass

    if df.shape[1] >= 2 and np.issubdtype(df.iloc[:,1].dtype, np.number):
        summary = summarize_grouped(df.iloc[:, :2].copy())
        out["suggested_chart"] = suggest_chart(df)
        out["insights"] = summary["bullets"]
        out["details"] = summary
        return out

    # Fallback
    out["suggested_chart"] = "table"
    out["insights"] = ["Returned a table. Inspect columns for detailed analysis."]
    out["details"] = {"columns": df.columns.tolist(), "row_count": len(df)}
    return out

