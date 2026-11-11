"""Script step 2 of the Tableau Prep flow: AI-READY CUSTOMER FEATURES (RFM) as Python functions.

    rfm_features(df)   one row per customer -> Recency, Frequency, Monetary, 1-5 scores, segment

Prep Script step settings: Connection = Tableau Python (TabPy) Server (localhost:9004),
File = this file, Function = rfm_features.
The same functions run on their own in tests/test_pipeline_functions.py.
"""
import os
from datetime import datetime
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------- RFM features (AI-ready)

SEGMENTS = [  # (name, condition on R and F scores) - first match wins
    ("Champions", lambda r, f: (r >= 4) & (f >= 4)),
    ("Loyal", lambda r, f: (r >= 3) & (f >= 4)),
    ("New or promising", lambda r, f: (r >= 4) & (f <= 2)),
    ("At risk", lambda r, f: (r <= 2) & (f >= 3)),
    ("Lost", lambda r, f: (r <= 2) & (f <= 2)),
]


def to_datetime(values):
    """Tableau Prep sends date-times as Java text, e.g. '2010-12-01T08:26:00Z[UTC]'.
    Remove the '[UTC]' zone label, read the rest, and drop the time zone (all times are UK)."""
    if pd.api.types.is_numeric_dtype(values):
        return pd.to_datetime(values, unit="ms", errors="coerce")
    text = values.astype("string").str.replace(r"\[.*\]$", "", regex=True)
    return pd.to_datetime(text, errors="coerce", utc=True, format="mixed").dt.tz_localize(None)


def score_1_to_5(values, higher_is_better=True):
    """Quintile score 1..5 by rank (ties broken by order, so every run gives the same score)."""
    ranks = values.rank(method="first", ascending=higher_is_better)
    return pd.qcut(ranks, 5, labels=[1, 2, 3, 4, 5]).astype(int)


def rfm_features(df):
    """Script step 2. Input: one row per customer (aggregated in Prep).
    Output: Recency, Frequency, Monetary values, 1-5 scores and a segment name."""
    out = df.copy()
    new_columns = ["recency_days", "avg_order_value_gbp", "r_score", "f_score", "m_score", "rfm_score", "segment"]
    if out.empty:  # Prep first calls the step with no rows to check it
        return out.assign(**{c: pd.Series(dtype="object") for c in new_columns})
    # Tableau Prep sends the rows in a different order on every run. Sorting first makes the
    # tie-breaking in the scores identical on every run (found by the reproducibility check).
    out = out.sort_values("customer_id", kind="stable").reset_index(drop=True)
    last = to_datetime(out["last_purchase"])
    reference_day = last.max().normalize() + pd.Timedelta(days=1)   # the day after the last sale
    out["recency_days"] = (reference_day - last.dt.normalize()).dt.days
    out["avg_order_value_gbp"] = (out["revenue_gbp"] / out["invoices"]).round(2)
    out["r_score"] = score_1_to_5(out["recency_days"], higher_is_better=False)  # recent = good
    out["f_score"] = score_1_to_5(out["invoices"])
    out["m_score"] = score_1_to_5(out["revenue_gbp"])
    out["rfm_score"] = out["r_score"] * 100 + out["f_score"] * 10 + out["m_score"]
    segment = pd.Series("Needs attention", index=out.index, dtype="object")
    for name, rule in reversed(SEGMENTS):
        segment = segment.mask(rule(out["r_score"], out["f_score"]), name)
    out["segment"] = segment
    write_run_log("rfm_features", len(out), out["segment"].value_counts().to_dict())
    return out


# ---------------------------------------------------------------- run log (evidence)

def write_run_log(step, rows, counts):
    """Append one line per Script-step run to logs/pipeline_run_log.txt."""
    project = Path(os.environ.get("RETAIL_PROJECT", os.getcwd()))
    log = project / "logs" / "pipeline_run_log.txt"
    try:
        log.parent.mkdir(exist_ok=True)
        with open(log, "a") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {step}: {rows} rows  {counts}\n")
    except OSError:
        pass  # logging must never break the flow


# ---------------------------------------------------------------- output schema for Tableau Prep
# Tableau Prep calls get_output_schema() to learn the output columns. prep_string(), prep_int() ...
# exist only inside Tableau Prep, so they are written out literally.

def get_output_schema():
    return pd.DataFrame({
        "customer_id": prep_string(), "country": prep_string(), "first_purchase": prep_datetime(),  # noqa: F821
        "last_purchase": prep_datetime(), "invoices": prep_int(), "order_lines": prep_int(),  # noqa: F821
        "products": prep_int(), "revenue_gbp": prep_decimal(), "recency_days": prep_int(),  # noqa: F821
        "avg_order_value_gbp": prep_decimal(), "r_score": prep_int(), "f_score": prep_int(),  # noqa: F821
        "m_score": prep_int(), "rfm_score": prep_int(), "segment": prep_string(),  # noqa: F821
    })
