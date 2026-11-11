"""PROFILING (read-only): measure the RAW data before anything is cleaned.

    python profiling/profile_raw.py

Profiling is diagnosis, not treatment: this script changes no data. It reads the two raw
sheets and the country file exactly as downloaded and writes
    reports/profiling.md          all tables below, readable
    reports/profiling_*.csv       column profile, KPIs, rules, structure checks
    reports/figures/profile_*.png charts for the slides
The cleaning itself happens only in the Tableau Prep flow.
"""
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
REP = ROOT / "reports"
FIG = REP / "figures"

BLUE, ORANGE, GREY, INK, INK2 = "#2a78d6", "#eb6834", "#b8b6ae", "#0b0b0b", "#52514e"
plt.rcParams.update({
    "figure.dpi": 150, "font.size": 10, "axes.edgecolor": GREY, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#ecebe7", "grid.linewidth": 0.8, "axes.axisbelow": True,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlecolor": INK,
})
SHEETS = ["Year 2009-2010", "Year 2010-2011"]


def md_table(df):
    cols = list(df.columns)
    out = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(str(v).replace("|", "/") for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(out)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / name, facecolor="white")
    plt.close(fig)


def load():
    sheets = pd.read_excel(RAW / "online_retail_II.xlsx", sheet_name=SHEETS)
    frames = [df.assign(sheet=name) for name, df in sheets.items()]
    sales = pd.concat(frames, ignore_index=True)
    rows = [line.rstrip("\n").split("\t") for line in open(RAW / "countryInfo.txt", encoding="utf-8")]
    comments = sum(1 for r in rows if r[0].startswith("#"))
    countries = pd.DataFrame([r for r in rows if not r[0].startswith("#")]).rename(
        columns={0: "iso2", 1: "iso3", 4: "country_name", 7: "population", 8: "continent_code"})
    return sheets, sales, countries, comments


def column_profile(df):
    rows = []
    for c in df.columns:
        s = df[c]
        if pd.api.types.is_numeric_dtype(s) or pd.api.types.is_datetime64_any_dtype(s):
            summary = f"min {s.min()} / max {s.max()}"
        else:
            top = s.astype(str).value_counts()
            summary = f"top {top.index[0][:30]!r} ({top.iloc[0]:,})"
        rows.append({"column": c, "type": str(s.dtype), "missing": int(s.isna().sum()),
                     "missing_%": round(100 * s.isna().mean(), 2), "distinct": int(s.nunique()),
                     "min / max or top value": summary})
    return pd.DataFrame(rows)


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    sheets, sales, countries, comments = load()
    business = ["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "Customer ID", "Country"]
    n = len(sales)
    inv = sales["Invoice"].astype(str)
    code = sales["StockCode"].astype(str)
    is_cancel = inv.str.startswith("C")
    is_product = code.str.match(r"^\d{5}")

    # ---------------- column analysis
    colprof = column_profile(sales[business])
    colprof.to_csv(REP / "profiling_column_profile.csv", index=False)

    # ---------------- KPIs (Lab 2.1 formulas)
    dup_all = sales.duplicated(subset=business)
    a, b = sheets[SHEETS[0]], sheets[SHEETS[1]]
    overlap = a.merge(b, on=business, how="inner")
    rules = {
        "R1 invoice is 6 digits (optionally C)": inv.str.match(r"^C?\d{6}$"),
        "R2 description present": sales["Description"].notna(),
        "R3 unit price > 0": sales["Price"] > 0,
        "R4 quantity > 0 on a sale": is_cancel | (sales["Quantity"] > 0),
        "R5 date inside 2009-12-01..2011-12-31": sales["InvoiceDate"].between("2009-12-01", "2011-12-31 23:59"),
        "R6 cancellation has negative quantity": ~is_cancel | (sales["Quantity"] < 0),
        "country is a real country in the reference": sales["Country"].isin(
            set(countries["country_name"]) | {"EIRE", "USA", "RSA", "Korea", "Czech Republic", "Netherlands"}),
    }
    kpis = pd.DataFrame([
        ("Completeness (8 columns)", round(100 * sales[business].notna().to_numpy().mean(), 2)),
        ("Completeness of Customer ID", round(100 * sales["Customer ID"].notna().mean(), 2)),
        ("Duplication: identical lines", round(100 * dup_all.mean(), 2)),
        ("Validity: 7 rules", round(100 * sum(r.sum() for r in rules.values()) / (n * len(rules)), 2)),
        ("Timeliness: last sale in the file", str(sales["InvoiceDate"].max())),
    ], columns=["KPI", "value"])
    kpis.to_csv(REP / "profiling_kpis.csv", index=False)
    rules_tbl = pd.DataFrame({"rule": list(rules), "failing rows": [int((~r).sum()) for r in rules.values()],
                              "passing %": [round(100 * r.mean(), 2) for r in rules.values()]})
    rules_tbl.to_csv(REP / "profiling_rules.csv", index=False)

    # ---------------- structure analysis
    descr = sales.dropna(subset=["Description"]).groupby("StockCode")["Description"].nunique()
    cust_country = sales.dropna(subset=["Customer ID"]).groupby("Customer ID")["Country"].nunique()
    line_key = sales.duplicated(subset=["Invoice", "StockCode"], keep=False)
    ref_names = set(countries["country_name"])
    unmatched = sales.loc[~sales["Country"].isin(ref_names), "Country"].value_counts()
    structure = pd.DataFrame([
        ("Invoice + StockCode is a unique key?", "no", f"{int(line_key.sum()):,} lines share invoice + product"),
        ("FD StockCode -> Description", "violated", f"{int((descr > 1).sum()):,} of {len(descr):,} products have more than one description"),
        ("FD Customer ID -> Country", "violated" if (cust_country > 1).any() else "holds",
         f"{int((cust_country > 1).sum())} customers appear with more than one country"),
        ("Overlap between the two sheets", "yes", f"{len(overlap):,} identical lines in both sheets (December 2010)"),
        ("Inclusion: Country in reference table (exact name)", "violated",
         ", ".join(f"{c} ({v:,})" for c, v in unmatched.items())),
        ("Reference table: comment lines before the data", "yes", f"{comments} lines start with '#'"),
    ], columns=["check", "result", "evidence"])
    structure.to_csv(REP / "profiling_structure.csv", index=False)

    # ---------------- distributions
    price = sales.loc[is_product & ~is_cancel & (sales["Price"] > 0), "Price"]
    q1, q3 = price.quantile([0.25, 0.75])
    iqr = q3 - q1
    non_product = code[~is_product & ~is_cancel].value_counts().head(10)
    per_month = sales.assign(month=sales["InvoiceDate"].dt.to_period("M").dt.to_timestamp()) \
        .groupby(["month", "sheet"]).size().unstack(fill_value=0)

    # ---------------- figures
    miss = colprof.set_index("column")["missing_%"].sort_values()
    fig, ax = plt.subplots(figsize=(7, 3.4))
    ax.barh(miss.index, miss.values, color=[ORANGE if v > 1 else BLUE for v in miss.values], height=0.6)
    for i, v in enumerate(miss.values):
        ax.text(v + 0.4, i, f"{v:.1f}%", va="center", fontsize=8, color=INK2)
    ax.set_xlim(0, max(miss.max() * 1.25, 5))
    ax.set_xlabel("missing values (% of 1,067,371 lines)")
    ax.set_title("Missing values per column (raw)")
    save(fig, "profile_missing_values.png")

    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.plot(per_month.index, per_month[SHEETS[0]], color=BLUE, lw=2, label="sheet Year 2009-2010")
    ax.plot(per_month.index, per_month[SHEETS[1]], color=ORANGE, lw=2, label="sheet Year 2010-2011")
    ax.axvspan(pd.Timestamp("2010-12-01"), pd.Timestamp("2010-12-31"), color=GREY, alpha=0.35)
    ax.text(pd.Timestamp("2010-12-05"), per_month.to_numpy().max() * 0.95, "Dec 2010 in BOTH sheets",
            fontsize=8, color=INK)
    ax.set_ylabel("order lines per month")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.set_title("The two sheets overlap in December 2010")
    save(fig, "profile_lines_per_month.png")

    fig, ax = plt.subplots(figsize=(7, 3.4))
    ax.hist(np.log10(price), bins=80, color=BLUE)
    ax.axvline(np.log10(q3 + 1.5 * iqr), color=ORANGE, lw=2)
    ax.text(np.log10(q3 + 1.5 * iqr) + 0.05, ax.get_ylim()[1] * 0.8,
            f"global IQR fence\n{q3 + 1.5 * iqr:.2f} GBP", fontsize=8)
    ticks = [0.01, 0.1, 1, 10, 100, 1000, 10000]
    ax.set_xticks(np.log10(ticks), [str(t) for t in ticks])
    ax.set_xlabel("unit price in GBP (log scale)")
    ax.set_ylabel("lines")
    ax.set_title(f"Unit prices: median {price.median():.2f} GBP, max {price.max():,.0f} GBP")
    save(fig, "profile_price_distribution.png")

    fig, ax = plt.subplots(figsize=(7, 3.4))
    s = non_product.sort_values()
    ax.barh(s.index, s.values, color=ORANGE, height=0.6)
    for i, v in enumerate(s.values):
        ax.text(v + 20, i, f"{v:,}", va="center", fontsize=8, color=INK2)
    ax.set_xlim(0, s.max() * 1.2)
    ax.set_xlabel("lines")
    ax.set_title("Not products: postage, fees and manual entries in StockCode")
    save(fig, "profile_non_product_codes.png")

    # ---------------- cleaning plan
    plan = pd.DataFrame([
        (1, "Identical lines, incl. Dec 2010 in both sheets", f"{int(dup_all.sum()):,}", "Tableau Prep: Aggregate on all columns (keep 1, count copies)"),
        (2, "Customer ID missing", f"{int(sales['Customer ID'].isna().sum()):,}", "keep for revenue, exclude from customer features (flag has_customer)"),
        (3, "Cancellations (invoice C...)", f"{int(is_cancel.sum()):,}", "separate output, not an error"),
        (4, "Postage / fees / manual codes in StockCode", f"{int((~is_product & ~is_cancel).sum()):,}", "separate output 'non_product'"),
        (5, "Price 0 or negative", f"{int((sales['Price'] <= 0).sum()):,}", "quarantine (rule R3)"),
        (6, "Missing description", f"{int(sales['Description'].isna().sum()):,}", "quarantine (rule R2)"),
        (7, "StockCode with several descriptions", f"{int((descr > 1).sum()):,} products", "dim_product: most used description"),
        (8, "Country names not standard (EIRE, RSA, USA ...)", f"{int(unmatched.sum()):,}", "Prep CASE mapping, then join reference"),
        (9, "Extreme prices (max 38,970 GBP)", "see IQR", "flag per product (IQR + 3x median), keep"),
        (10, "Text: double spaces, trailing spaces", "-", "TRIM, one space, upper case"),
    ], columns=["#", "issue", "rows", "action in the Tableau Prep flow"])

    report = f"""# Profiling report - raw data (before cleaning)

Generated by `profiling/profile_raw.py`. Read-only: nothing in `data/raw/` was changed.

## Size
| table | rows | columns |
|---|---|---|
| sheet Year 2009-2010 | {len(a):,} | {a.shape[1]} |
| sheet Year 2010-2011 | {len(b):,} | {b.shape[1]} |
| **sales total** | **{n:,}** | 8 |
| countryInfo.txt (GeoNames) | {len(countries):,} countries + {comments} comment lines | 19 |

Distinct: {inv.nunique():,} invoices, {code.nunique():,} stock codes, {sales['Customer ID'].nunique():,} customers, {sales['Country'].nunique()} countries.
Period: {sales['InvoiceDate'].min()} to {sales['InvoiceDate'].max()}.

## Quality KPIs (raw)
{md_table(kpis)}

## Validity rules (raw)
{md_table(rules_tbl)}

## Column profile
{md_table(colprof)}

## Structure analysis
{md_table(structure)}

## Unit price (product sale lines with price > 0)
Q1 = {q1:.2f} GBP, Q3 = {q3:.2f} GBP, IQR = {iqr:.2f}, upper fence = {q3 + 1.5 * iqr:.2f} GBP.
{int((price > q3 + 1.5 * iqr).sum()):,} lines lie above this *global* fence - mostly normal expensive products.
That is why the flow checks prices **per product** instead.

## Most common non-product codes
{md_table(non_product.rename_axis('StockCode').reset_index(name='lines'))}

## Cleaning plan (input for the Tableau Prep flow)
{md_table(plan)}
"""
    (REP / "profiling.md").write_text(report)
    print(report[:1500])


if __name__ == "__main__":
    main()
