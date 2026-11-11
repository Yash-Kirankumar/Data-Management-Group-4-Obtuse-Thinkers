"""Script step 1 of the Tableau Prep flow: DATA-QUALITY RULES written as Python functions.

Tableau Prep does the visual cleaning (types, names, duplicates, union, join, calculated
fields, aggregation). The quality rules must be *code* - versioned, tested, identical on
every run - so they live here as small functions:

    apply_quality_rules(df)   every sales line gets dq_status + dq_reason + price_outlier_iqr

Prep Script step settings: Connection = Tableau Python (TabPy) Server (localhost:9004),
File = this file, Function = apply_quality_rules. Prep sends the step's rows as a pandas
DataFrame and uses the returned DataFrame as the step's output.
The same functions run on their own in tests/test_pipeline_functions.py.
"""
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- the rules, in one place

FIRST_DAY = pd.Timestamp("2009-12-01")          # the shop's data starts here
LAST_DAY = pd.Timestamp("2011-12-31")           # and ends in December 2011
INVOICE_PATTERN = r"^C?\d{6}$"                  # 6 digits; a leading C = cancellation
MIN_LINES_FOR_PRICE_CHECK = 10                  # IQR needs enough prices per product
PRICE_JUMP = 3                                  # outlier must also be 3x (or 1/3 of) the median

DQ_STATUSES = ["trusted", "quarantine", "cancellation", "non_product"]


def to_datetime(values):
    """Tableau Prep sends date-times as Java text, e.g. '2010-12-01T08:26:00Z[UTC]'.
    Remove the '[UTC]' zone label, read the rest, and drop the time zone (all times are UK)."""
    if pd.api.types.is_numeric_dtype(values):
        return pd.to_datetime(values, unit="ms", errors="coerce")
    text = values.astype("string").str.replace(r"\[.*\]$", "", regex=True)
    return pd.to_datetime(text, errors="coerce", utc=True, format="mixed").dt.tz_localize(None)


def quality_reason(df):
    """Return the FIRST broken rule for every row ('' = no rule broken).

    Rules for sales lines (cancellations are checked separately):
      R1 invoice number must be 6 digits (optionally with C)   -> validity
      R2 description must not be empty                          -> completeness
      R3 unit price must be above 0                             -> validity
      R4 quantity must be above 0 on a sale                     -> validity
      R5 date must lie inside the shop's data period            -> validity / timeliness
      R6 a cancellation (C...) must have a negative quantity    -> consistency
    """
    reason = pd.Series("", index=df.index, dtype="object")
    invoice = df["invoice"].astype(str)
    is_cancel = invoice.str.startswith("C")
    when = to_datetime(df["invoice_datetime"])

    checks = [  # (row breaks the rule, reason) - the first match wins
        (~invoice.str.match(INVOICE_PATTERN), "R1 invoice number not 6 digits (e.g. A-adjustment)"),
        (df["description"].isna() | (df["description"].astype(str).str.strip() == ""),
         "R2 missing description"),
        (df["unit_price_gbp"].fillna(0) <= 0, "R3 unit price is 0 or negative"),
        (~is_cancel & (df["quantity"].fillna(0) <= 0), "R4 quantity 0 or negative on a sale"),
        (when.isna() | (when < FIRST_DAY) | (when > LAST_DAY), "R5 date outside 2009-12-01..2011-12-31"),
        (is_cancel & (df["quantity"].fillna(0) >= 0), "R6 cancellation with positive quantity"),
    ]
    for broken, text in reversed(checks):   # reversed, so the first rule overwrites the later ones
        reason = reason.mask(broken, text)
    return reason


def price_outlier_flag(df):
    """Price outlier per product = BOTH
         (a) outside the IQR fence of that product's prices: < Q1 - 1.5*IQR or > Q3 + 1.5*IQR
         (b) at least 3x the product's median price (or at most 1/3 of it).
    Why (b)? This is a wholesale shop: one product is sold at a few quantity-discount prices.
    Most products have one dominant price, so their IQR is 0 and plain IQR would flag every
    normal discount (15% of all lines). Requiring a 3x jump keeps only real anomalies.
    A rule flags, a human decides: flagged rows stay in the data."""
    price = df["unit_price_gbp"]
    grp = df.groupby("stock_code")["unit_price_gbp"]
    q1 = grp.transform(lambda p: p.quantile(0.25))
    q3 = grp.transform(lambda p: p.quantile(0.75))
    median, n = grp.transform("median"), grp.transform("size")
    iqr = q3 - q1
    high = (price > q3 + 1.5 * iqr) & (price >= PRICE_JUMP * median)
    low = (price < q1 - 1.5 * iqr) & (price <= median / PRICE_JUMP)
    return ((high | low) & (n >= MIN_LINES_FOR_PRICE_CHECK)).fillna(False)


def classify(df):
    """dq_status: trusted / quarantine / cancellation / non_product."""
    reason = quality_reason(df)
    status = np.select(
        [reason != "", df["line_type"] == "cancellation", df["line_type"] == "non_product"],
        ["quarantine", "cancellation", "non_product"], default="trusted")
    return pd.Series(status, index=df.index), reason


def apply_quality_rules(df):
    """Script step 1. Input: all de-duplicated, cleaned sales lines. Output: the same rows
    plus dq_status, dq_reason and price_outlier_iqr. Rows are never dropped here -
    Tableau Prep splits them into trusted / quarantine / cancellation / non_product outputs."""
    out = df.copy()
    out["dq_status"], out["dq_reason"] = classify(out)
    product_sales = out["dq_status"] == "trusted"
    flags = pd.Series(False, index=out.index)
    flags[product_sales] = price_outlier_flag(out[product_sales])
    out["price_outlier_iqr"] = flags.astype(bool)
    write_run_log("apply_quality_rules", len(out), out["dq_status"].value_counts().to_dict())
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
        "invoice": prep_string(), "stock_code": prep_string(), "description": prep_string(),  # noqa: F821
        "quantity": prep_int(), "invoice_datetime": prep_datetime(), "unit_price_gbp": prep_decimal(),  # noqa: F821
        "customer_id": prep_string(), "country_raw": prep_string(), "country": prep_string(),  # noqa: F821
        "source_sheet": prep_string(), "copies": prep_int(), "invoice_date": prep_date(),  # noqa: F821
        "invoice_month": prep_date(), "is_cancellation": prep_bool(), "line_type": prep_string(),  # noqa: F821
        "line_revenue_gbp": prep_decimal(), "has_customer": prep_bool(),  # noqa: F821
        "dq_status": prep_string(), "dq_reason": prep_string(), "price_outlier_iqr": prep_bool(),  # noqa: F821
    })
