# Data dictionary

Every column of every output of the Tableau Prep flow.
**Source:** *raw* = from the UCI file (cleaned); *ref* = from the GeoNames reference table; *derived* = calculated in the flow; *script* = calculated in a Python Script step.

## fact_sales.csv / fact_sales.hyper - one row per unique trusted sales line (1,003,214 rows)
`quarantine_lines.csv`, `cancellations.csv` and `non_product_lines.csv` have the same 26 columns.

| Column | Meaning | Type / unit | Rule | Source |
|---|---|---|---|---|
| invoice | invoice number; a "C" in front = cancellation | text, 6 digits | R1: `^C?\d{6}$` | raw `Invoice` (read as text in the Input step, trimmed, upper case) |
| stock_code | product code | text | 5 digits (+ letter) = product | raw `StockCode` (trimmed, upper case) |
| description | product name | text, upper case, single spaces | R2: not empty | raw `Description` |
| quantity | items on this line | whole number | R4: > 0 on a sale, R6: < 0 on a cancellation | raw `Quantity` |
| unit_price_gbp | price per item | **GBP** | R3: > 0 | raw `Price` |
| line_revenue_gbp | quantity × unit price, rounded to pence | **GBP** | - | derived |
| invoice_datetime | date and time of the invoice | ISO 8601 text `YYYY-MM-DD hh:mm:ss`, UK time | R5: 2009-12-01 to 2011-12-31 | raw `InvoiceDate` |
| invoice_date | the date only | `YYYY-MM-DD` | - | derived |
| invoice_month | first day of the month | `YYYY-MM-01` | - | derived |
| customer_id | customer number | text (e.g. `13085`) or empty | may be empty (22.6% of lines) | raw `Customer ID` (number → text) |
| has_customer | customer_id is filled | true/false | - | derived |
| country_raw | country exactly as in the source | text | - | raw `Country` |
| country | standardised country name (GeoNames spelling) | text or empty | "Unspecified" → empty | derived (CASE mapping) |
| iso2 / iso3 | ISO 3166-1 country code | 2 / 3 letters | - | ref |
| continent_code / continent | continent | code / name | - | ref |
| population | country population (GeoNames) | people | - | ref |
| country_matched | the country was found in the reference table | true/false | - | derived |
| is_cancellation | invoice starts with "C" | true/false | - | derived |
| line_type | product / non_product / cancellation | text | product = stock code starts with 5 digits | derived |
| dq_status | trusted / quarantine / cancellation / non_product | text | - | script (rules R1-R6) |
| dq_reason | first broken rule, empty if none | text | - | script |
| price_outlier_iqr | price outside the product's IQR fence **and** ≥ 3× (or ≤ ⅓) its median | true/false | flag only, the row stays | script |
| copies | how many identical raw lines were merged into this row | whole number ≥ 1 | - | derived (duplicate removal) |
| source_sheet | lineage: workbook and sheet the row came from (first copy) | text | - | derived (Prep "Table Names") |

## dim_product.csv - one row per product (4,707 rows)
| Column | Meaning |
|---|---|
| stock_code | product code (key) |
| description | the most used description of this product (ties: alphabetically first) |
| descriptions_found | how many different descriptions the product had in the raw data |
| lines_with_this_description | sales lines that used this description |

## monthly_revenue.csv - one row per month × country (562 rows)
| Column | Meaning |
|---|---|
| invoice_month | `YYYY-MM-01` |
| country / continent | standardised country, continent (empty = not a real country) |
| revenue_gbp | sum of line revenue, GBP, rounded to pence |
| invoices | number of different invoices |
| units | items sold |
| customers | number of different customers (lines without a customer are not counted) |

## customer_features.csv - one row per customer, AI-ready (5,852 rows)
| Column | Meaning | Unit |
|---|---|---|
| customer_id | customer (key) | text |
| country | the customer's country (alphabetically first if several) | text |
| first_purchase / last_purchase | first / last invoice | ISO 8601 |
| invoices | **F**requency: number of different invoices | count |
| order_lines | number of sales lines | count |
| products | number of different products bought | count |
| revenue_gbp | **M**onetary: total spent | GBP |
| recency_days | **R**ecency: days from the last purchase to 2011-12-10 (the day after the last sale) | days |
| avg_order_value_gbp | revenue / invoices | GBP |
| r_score, f_score, m_score | 1-5 quintile scores (5 = best: recent, frequent, high spend) | 1-5 |
| rfm_score | r×100 + f×10 + m (e.g. 555 = best) | - |
| segment | Champions, Loyal, New or promising, At risk, Lost, Needs attention | text |

## Process files
- `data/output/_manifest.json`: raw row counts, rows per output, copies, reconciliation, KPIs and fingerprints.
- `logs/pipeline_run_log.txt`: one line per Script-step run.
- `data/raw/_download_manifest.json`: SHA-256 of the raw files.
