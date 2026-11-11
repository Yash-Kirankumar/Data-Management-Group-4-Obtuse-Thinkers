"""Charts of the RESULTS (read-only, run after the Tableau Prep flow) for slides and report.

    python tools/results_figures.py     -> reports/figures/result_*.png
"""
import json
import sys
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "profiling"))
from profile_raw import BLUE, GREY, INK, INK2, ORANGE, save  # noqa: E402  (same chart style)

OUT = ROOT / "data" / "output"


def read(name):
    return pd.read_csv(OUT / name, encoding="utf-8-sig")


def main():
    m = read("monthly_revenue.csv")
    m["invoice_month"] = pd.to_datetime(m["invoice_month"])

    # 1. Revenue per month
    per_month = m.groupby("invoice_month")["revenue_gbp"].sum() / 1000
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.plot(per_month.index[:-1], per_month.values[:-1], color=BLUE, lw=2)
    ax.plot(per_month.index[-2:], per_month.values[-2:], color=GREY, lw=2, ls="--")
    ax.text(per_month.index[-1], per_month.values[-1], "  9 days only", fontsize=8, color=INK2, va="center")
    top = per_month.idxmax()
    ax.annotate(f"peak {top:%b %Y}: {per_month.max():,.0f}k GBP", xy=(top, per_month.max()),
                xytext=(pd.Timestamp("2010-04-01"), per_month.max() * 0.95), fontsize=8, color=INK,
                arrowprops=dict(arrowstyle="-", color=INK2))
    ax.set_ylabel("revenue (thousand GBP)")
    ax.set_title("Monthly revenue, trusted sales lines - peaks before Christmas")
    save(fig, "result_revenue_per_month.png")

    # 2. Revenue by country (top 10, UK separately named)
    by_country = m.groupby("country", dropna=False)["revenue_gbp"].sum().sort_values(ascending=False)
    share_uk = by_country.get("United Kingdom", 0) / by_country.sum() * 100
    top10 = by_country.drop("United Kingdom", errors="ignore").head(10).sort_values() / 1000
    fig, ax = plt.subplots(figsize=(7.5, 4))
    ax.barh(top10.index.fillna("(unknown)"), top10.values, color=BLUE, height=0.6)
    for i, v in enumerate(top10.values):
        ax.text(v + 5, i, f"{v:,.0f}k", va="center", fontsize=8, color=INK2)
    ax.set_xlim(0, top10.max() * 1.18)
    ax.set_xlabel("revenue (thousand GBP)")
    ax.set_title(f"Top 10 export countries (United Kingdom alone = {share_uk:.0f}% of revenue)")
    save(fig, "result_revenue_by_country.png")

    # 3. RFM segments
    c = read("customer_features.csv")
    seg = c.groupby("segment").agg(customers=("customer_id", "size"), revenue=("revenue_gbp", "sum"))
    seg["revenue_%"] = seg["revenue"] / seg["revenue"].sum() * 100
    seg = seg.sort_values("customers")
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    ax.barh(seg.index, seg["customers"], color=BLUE, height=0.6)
    for i, (n, p) in enumerate(zip(seg["customers"], seg["revenue_%"])):
        ax.text(n + 20, i, f"{n:,} customers, {p:.0f}% of revenue", va="center", fontsize=8, color=INK2)
    ax.set_xlim(0, seg["customers"].max() * 1.6)
    ax.set_xlabel("customers")
    ax.set_title("Customer segments from the RFM Script step")
    save(fig, "result_rfm_segments.png")

    # 4. Where did every raw line go?
    v = json.loads((OUT / "_manifest.json").read_text())
    parts = [("trusted sales", v["rows_per_output"]["fact_sales.csv"], BLUE),
             ("duplicates removed", v["duplicates_removed"], GREY),
             ("cancellations", v["rows_per_output"]["cancellations.csv"], ORANGE),
             ("quarantine", v["rows_per_output"]["quarantine_lines.csv"], ORANGE),
             ("non-product (postage, fees)", v["rows_per_output"]["non_product_lines.csv"], ORANGE)]
    fig, ax = plt.subplots(figsize=(7.5, 3.2))
    for i, (label, n, col) in enumerate(reversed(parts)):
        ax.barh(label, n, color=col, height=0.6)
        ax.text(n + 8000, i, f"{n:,}", va="center", fontsize=8, color=INK2)
    ax.set_xscale("log")
    ax.set_xlim(1000, 4e6)
    ax.set_xlabel(f"lines (log scale) - together exactly the {v['raw_total']:,} raw lines")
    ax.set_title("Where every raw line went")
    save(fig, "result_where_lines_went.png")
    print("figures written to reports/figures/")


if __name__ == "__main__":
    main()
