"""The Script-step functions run ON THEIR OWN, on a few hand-made rows.

    .venv/bin/python -m pytest tests

If a rule is wrong, a test fails here - before the rule touches a million real lines
inside Tableau Prep.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "prep"))
import script_quality_rules as q  # noqa: E402
import script_rfm_features as r  # noqa: E402


def line(**kw):
    base = {"invoice": "489434", "stock_code": "85048", "description": "ROSE CUSHION", "quantity": 12,
            "invoice_datetime": "2009-12-01T07:45:00Z[UTC]", "unit_price_gbp": 6.95,
            "line_type": "product", "customer_id": "13085"}
    base.update(kw)
    return base


def test_tableau_date_format_is_read():
    d = q.to_datetime(pd.Series(["2010-09-14T16:25:00Z[UTC]", None]))
    assert d.iloc[0] == pd.Timestamp("2010-09-14 16:25") and pd.isna(d.iloc[1])


def test_each_rule_gives_its_reason():
    df = pd.DataFrame([
        line(),                                                    # good sale
        line(invoice="A563185"),                                   # R1
        line(description=None),                                    # R2
        line(unit_price_gbp=0.0),                                  # R3
        line(quantity=-3),                                         # R4
        line(invoice_datetime="2012-02-01T10:00:00Z[UTC]"),        # R5
        line(invoice="C489449", quantity=5, line_type="cancellation"),   # R6
        line(invoice="C489449", quantity=-5, line_type="cancellation"),  # a real cancellation
        line(stock_code="POST", line_type="non_product"),          # postage
    ])
    status, reason = q.classify(df)
    assert list(reason.str[:2]) == ["", "R1", "R2", "R3", "R4", "R5", "R6", "", ""]
    assert list(status) == ["trusted", "quarantine", "quarantine", "quarantine", "quarantine",
                            "quarantine", "quarantine", "cancellation", "non_product"]


def test_first_broken_rule_wins():
    df = pd.DataFrame([line(description=None, unit_price_gbp=0.0)])   # breaks R2 and R3
    assert q.quality_reason(df).iloc[0].startswith("R2")


def test_price_outlier_needs_iqr_and_3x_median():
    prices = [1.0] * 12 + [2.5, 40.0]       # 2.5 = normal discount tier, 40 = anomaly
    df = pd.DataFrame({"stock_code": "X", "unit_price_gbp": prices})
    flags = q.price_outlier_flag(df)
    assert list(flags) == [False] * 13 + [True]


def test_small_products_are_not_judged():
    df = pd.DataFrame({"stock_code": "Y", "unit_price_gbp": [1.0, 1.0, 50.0]})  # only 3 lines
    assert not q.price_outlier_flag(df).any()


def test_rfm_scores_and_segments():
    customers = pd.DataFrame({
        "customer_id": [str(i) for i in range(10)],
        "last_purchase": [f"2011-12-0{9 - i}T10:00:00Z[UTC]" if i < 5 else "2010-01-05T10:00:00Z[UTC]"
                          for i in range(10)],
        "invoices": [20, 18, 15, 12, 10, 1, 1, 2, 1, 1],
        "revenue_gbp": [5000, 4000, 3000, 2000, 1000, 50, 40, 60, 30, 20],
    })
    out = r.rfm_features(customers).set_index("customer_id")
    assert out.loc["0", "segment"] == "Champions"
    assert out.loc["5", "segment"] == "Lost"   # old purchase, 1 invoice, little money
    assert out[["r_score", "f_score", "m_score"]].isin([1, 2, 3, 4, 5]).all().all()


def test_rfm_is_independent_of_row_order():
    customers = pd.DataFrame({
        "customer_id": [str(i) for i in range(20)],
        "last_purchase": ["2011-12-01T10:00:00Z[UTC]"] * 20,    # all tied
        "invoices": [3] * 20, "revenue_gbp": [100.0] * 20,
    })
    a = r.rfm_features(customers).set_index("customer_id").sort_index()
    b = r.rfm_features(customers.sample(frac=1, random_state=1)).set_index("customer_id").sort_index()
    assert a.equals(b)


def test_empty_input_from_prep_preview():
    empty = pd.DataFrame(columns=["customer_id", "last_purchase", "invoices", "revenue_gbp"])
    assert "segment" in r.rfm_features(empty).columns
