# Online Retail II: the whole project, explained step by step

> **How to read this file.** It follows the order of the exam's slides
> (dataset → architecture → FAIR → profiling → Tableau Prep → pipeline → governance → conclusion).
> Every step answers the same questions:
>
> - **What** we did: the concrete action, and where it is in the project.
> - **Why**: the reason, in plain words. This is what the professor will ask about.
> - **How**: exactly how it is done (which Tableau Prep step, which click, which formula).
> - **Theory**: the idea from the lecture behind it (chapter in brackets).
> - **Result**: the real number we got.
>
> All numbers come from this project's own files and runs. Run it again and you get the same numbers (section 6.6).

---

## 0. The project on one page

**The exam question:** *"Can this data be trusted, reused and fed into an AI model, and how do you prove it?"*

**Our data:** the sales of a real UK online gift shop: 1,067,371 order lines from December 2009 to December 2011.
- Source: UCI Machine Learning Repository, "Online Retail II", licence CC BY 4.0.
- It comes as one Excel file with **two tables**, one per year.
- We add a third, small table: a **country reference list** (GeoNames, CC BY 4.0).

**Our problem statement:** the shop's managers want to know:
1. **how much revenue we make per month and per country**;
2. **which customers are likely to buy again** (customer segments that a model can use).

They can only use the raw sales export for this if it can be trusted.

**The rule of this project:**

| What | Where it happens |
|---|---|
| All **cleaning and transformation** | **Tableau Prep**: the flow `prep/online_retail_flow.tfl` |
| The **reproducible pipeline** (rules written as code) | Python functions **inside Tableau Prep's Script steps**: `prep/script_quality_rules.py`, `prep/script_rfm_features.py` |
| Downloading, measuring, checking | small Python helpers in `tools/` and `profiling/`. They **only read** data, never change it |

**The answer in one sentence:** yes. After the flow, every one of the 1,067,371 raw lines is accounted for:
- trusted, quarantined with a reason, a cancellation, a non-product line, or a removed duplicate;
- the trusted table is 99.99% complete, 100% valid and 0% duplicated;
- running the flow twice, or on new data, gives exactly the same result.

So the data can be trusted for reporting and for a customer model, **within documented limits**: 22.6% of lines have no customer, the UK is 85.5% of revenue, and the data ends in 2011.

| Exam part | Where in this file | Proof in the project |
|---|---|---|
| Dataset & problem | section 1 | `README.md`, `data/raw/_download_manifest.json` |
| Architecture | section 2 | diagram 2.1 |
| FAIR | section 3 | `fair/` |
| Profiling | section 4 | `reports/profiling.md`, `reports/figures/profile_*.png` |
| Cleaning in Tableau Prep | section 5 | `prep/online_retail_flow.tfl` (opens and runs in Tableau Prep) |
| Reproducible pipeline | section 6 | `prep/script_*.py`, `tests/`, `reports/reproducibility_check.md` |
| Governance | section 7 | `governance/` |
| Conclusion | section 8 | `reports/verification.md`, `reports/figures/result_*.png` |

---

## 1. Dataset and problem statement (slide 1)

### 1.1 Why this dataset
**What:** we use *Online Retail II* from the UCI Machine Learning Repository.

**Why:**
- **Easy to understand.** Every row is one line of a shop invoice: *who bought what, how many, for how much, when, from which country*. Only 8 columns. Anyone understands it in 10 seconds.
- **It is e-commerce,** the same world as the professor's own lab example (online shop orders in Chapter 2). Every lab idea fits directly: duplicates, union, join, revenue = quantity × price, outliers, quarantine.
- **It meets every exam rule** (table below).
- **Its problems are real, not made up.** The two tables overlap, cancellations are mixed with sales, postage is written as a "product", prices are 0 or 38,970, and customer IDs are missing.

| Exam rule | How Online Retail II meets it |
|---|---|
| at least 1,000 rows | **1,067,371** lines (53,628 invoices, 5,942 customers, 5,305 product codes) |
| two related tables | sheet **"Year 2009-2010"** (525,461 rows) and sheet **"Year 2010-2011"** (541,910 rows). Same 8 columns, the same customers and products appear in both. Plus the **GeoNames country table**, related through the country name |
| a date column | `InvoiceDate` (date and time of every invoice) |
| real quality problems | duplicates, overlap, missing customers, cancellations, prices ≤ 0, non-standard country names, products with several names (section 4) |
| an open licence | **CC BY 4.0** (UCI), and GeoNames is CC BY 4.0 too |
| allowed source | UCI is on the professor's list; it has a permanent **DOI 10.24432/C5CG6D** |

### 1.2 What the data looks like
| Column (in the file) | Meaning | Example |
|---|---|---|
| Invoice | invoice number; **C** in front = cancelled | `489434`, `C489449` |
| StockCode | product code | `85048`, `85123A`, `POST` |
| Description | product name | `WHITE HANGING HEART T-LIGHT HOLDER` |
| Quantity | how many items | `12`, `-12` (cancellation) |
| InvoiceDate | when | `2009-12-01 07:45` |
| Price | price per item, **in GBP** (pound sterling) | `6.95` |
| Customer ID | customer number | `13085` (sometimes empty) |
| Country | where the customer lives | `United Kingdom`, `EIRE` |

The third table, GeoNames `countryInfo.txt`, has one row per country: ISO codes (`GB`, `GBR`), name, capital, area, population, continent and more (19 columns).

### 1.3 The problem statement
> *The management of a UK online gift shop wants (1) reliable **monthly revenue per country** for planning and (2)
> **customer segments**: who are our best customers, who is about to leave. The segments should later feed
> a model that predicts who buys again. The question: **can the raw sales export be trusted for this, and how do we
> prove it?***

**Why this problem:**
- It has **real users** (managers, a data scientist) and two concrete products (a dashboard and a model).
- It **needs both tables** (both years) and the reference table (country codes and continents).
- It forces real **data management decisions**. What is a sale, a cancellation, or postage? What do we do with lines without a customer? Which of several product names is right?
- It has an honest **AI part**: RFM customer features are classic machine-learning input.

---

## 2. Architecture (slide 2)

### 2.1 The sketch from source to final dataset
```
 SOURCES                      RAW ZONE (data lake idea)     TRANSFORM: TABLEAU PREP FLOW                       OUTPUTS / WAREHOUSE              USE
 UCI repository  --HTTPS-->   data/raw/                --> Input (2 sheets + countries)                  --> data/output/*.csv          --> sales dashboard
 (online_retail_II.xlsx,      online_retail_II.xlsx        Union -> Clean -> Remove duplicates               fact_sales, quarantine,         (monthly revenue)
  DOI 10.24432/C5CG6D)        countryInfo.txt              -> Calculated fields                               cancellations, non_product,
 GeoNames        --HTTPS-->   _download_manifest.json      -> SCRIPT STEP 1 (Python: quality rules)          monthly_revenue, dim_product,
 (countryInfo.txt)            (SHA-256, never changed)     -> Join countries -> Split by quality status       customer_features          --> customer model
                                                            -> Aggregates -> SCRIPT STEP 2 (Python: RFM)   --> data/warehouse/              (RFM segments)
                                                            -> Outputs                                          fact_sales.hyper
                       Python helpers (read-only): download, profiling, verification, reproducibility check, tests
```

### 2.2 ETL, not ELT
**What:** our pipeline is **ETL**: **E**xtract → (profile) → **T**ransform in Tableau Prep → **L**oad into the output and warehouse.

**Why:**
- The cleaning decisions (what is a sale, what is quarantined) must happen **before** anyone uses the data. A dashboard must never see a duplicate or a 38,970 GBP postage line.
- Tableau Prep is a classic ETL tool: it reads, transforms in its own engine, then writes.
- The data is small (45 MB), so ELT's main advantage (load huge data fast first) doesn't matter.

**How we still keep ELT's safety:** the raw files stay **unchanged** in `data/raw/`, so we can re-run the transformation at any time. The professor's rule: "never overwrite the raw file".

**Theory (Ch. 1, Ch. 2):**
- ETL = transform before loading.
- ELT = load raw into the warehouse, transform there.
- Profiling belongs right after Extract: "Extract → Profile → Clean/Transform → Load".

### 2.3 Where the data is stored
| Layer | Where | What | Rule |
|---|---|---|---|
| **Raw zone** (lake idea) | `data/raw/` | files exactly as downloaded + SHA-256 checksums | read only, never written |
| **Processing** | inside Tableau Prep (and TabPy for the Script steps) | data in memory while the flow runs | not stored |
| **Output / warehouse** | `data/output/*.csv`, `data/warehouse/fact_sales.hyper` | trusted tables, quarantine, aggregates, AI features | rebuilt by every run |

**Why a `.hyper` file as the warehouse:**
- **Hyper** is Tableau's own analytical database engine (fast SQL, column storage).
- Tableau Prep writes it directly, and Tableau Desktop reads it directly for the dashboard.
- So the "load into the warehouse" step also happens inside Tableau. No extra Python is needed.

**Why CSV as well:** CSV is open and readable by any tool (pandas, Excel, R). That serves FAIR's Interoperability.

**Theory (Ch. 1):**
- A **data lake** stores raw data cheaply.
- A **warehouse** stores cleaned, structured data for analysis (OLAP).
- Our setup = raw zone + warehouse tables.
- In warehouse style, `fact_sales` is a **fact** table (one row per event, a sales line) and `dim_product` is a **dimension** (one row per thing, a product).

### 2.4 OLTP and OLAP
- **OLTP** (runs the business): the shop's order system, where every order is written as it happens. We only see its export.
- **OLAP** (understands the business): our outputs and dashboard. The OLAP question: *"How much revenue per month and country, and which customers are Champions or At risk?"*
- **The flow is the bridge** between the two.

### 2.5 Where Tableau Prep and Python run
| Part | Runs in | Why there |
|---|---|---|
| all visual cleaning (types, names, union, duplicates, calculations, join, splits, aggregates, outputs) | **Tableau Prep Builder 2026.2** | the course tool; every change is visible in the Changes pane |
| quality rules R1-R6, price-outlier rule, RFM scores | **Python inside Prep's Script step**, through **TabPy** (Tableau's Python server) on this computer | rules as *code*: versioned in Git, unit-tested, identical on every run (Ch. 3) |
| download, profiling, verification, charts, tests | Python on the command line | they only **read** data and measure it |

**What is TabPy:**
- A small server from Tableau that runs Python.
- When the flow reaches a Script step, Tableau Prep sends the rows to TabPy, TabPy runs our function, and Prep receives the new rows back.
- We start it with `tools/run_tabpy_local.py`, which forces it to listen **only on this computer (localhost)**. The security reason is in section 7.4.

### 2.6 The data lifecycle in our project (Ch. 1)
1. **Create:** customers place orders in the shop.
2. **Store:** the shop's system; UCI publishes the export; we keep it in `data/raw`.
3. **Process & integrate:** the Tableau Prep flow (union, clean, rules, join).
4. **Analyse:** monthly revenue, RFM segments, charts.
5. **Share:** CSV + Hyper outputs, metadata record, GitHub, Zenodo (planned).
6. **Preserve & reuse:** checksums, fingerprints, version 1.0.0, CC BY licence, the flow re-runs on new data.

---

## 3. FAIR (slide 3)

### 3.1 What FAIR means
**Theory (Ch. 1, Wilkinson et al. 2016):** FAIR = **F**indable, **A**ccessible, **I**nteroperable, **R**eusable. These are rules that make data usable by people **and machines**.

| | Means | Typical proof |
|---|---|---|
| **F** | it can be found | a persistent ID (DOI), rich metadata, listed in a catalogue |
| **A** | once found, it can be downloaded | a standard protocol (HTTPS), clear access rules, metadata stays available |
| **I** | it can be combined with other data | an open format (CSV), standard vocabularies (ISO codes, schema.org), units |
| **R** | a stranger can judge and reuse it | a licence, provenance (where from, what changed), documentation, quality info |

FAIR is **not** the same as "open": data can be FAIR with restricted access, as long as the rules are clear.

### 3.2 How we scored
**What:** the professor's Lab 1.2 scorecard. Each letter gets **0, 1 or 2**, so the total is out of **8**. File: `fair/fair_scorecard.md`.

| | Original UCI dataset | Why | Our cleaned v1.0.0 | What we did |
|---|---|---|---|---|
| **F** | **2** | DOI 10.24432/C5CG6D, UCI catalogue, title, description (only missing: keywords) | **1** (2 after Zenodo) | `fair/metadata.json` with 10 keywords; no DOI yet, because only publication gives one |
| **A** | **2** | HTTPS download, no login, permanent landing page | **1** (2 after Zenodo) | GitHub + download script with checksums; Zenodo planned |
| **I** | **1** | Excel instead of CSV; currency only in the web text; country names not standard (EIRE, RSA, USA) | **2** | UTF-8 CSV, ISO 8601 dates, `_gbp` in the column names, ISO 3166 country codes, schema.org |
| **R** | **1** | CC BY 4.0, **but the documentation does not match the file** (see 3.3); no quality info; overlap not documented | **2** | licence + credit kept; lineage in every row; the flow file *is* the cleaning log; data dictionary; KPIs |
| **Total** | **6 / 8** | | **6 / 8 → 8 / 8 after a DOI** | |

**Why the totals are equal but the story is not:**
- The original is good at **finding and downloading** (UCI gives a DOI), but weak at **combining and reusing**.
- Our version fixes exactly the weak part (I and R). F and A only need the publication step (Zenodo, TO CONFIRM by the group).
- Claiming 8/8 before publishing would be dishonest. The professor's own sample answer scores the same way.

### 3.3 The metadata record: what we found
**What:** we wrote the original dataset's metadata as a machine-readable **schema.org JSON-LD** record (`fair/original_metadata_record.json`). We wrote a second record for our cleaned dataset (`fair/metadata.json`).

**Why JSON-LD / schema.org:** it is the standard of the course. It is read by Google Dataset Search, and Croissant (the ML dataset standard) is built on it.

**What we found while writing it (a strong slide point):**

| UCI documentation says | The file really has |
|---|---|
| column `InvoiceNo` | `Invoice` |
| column `UnitPrice` | `Price` |
| column `CustomerID` | `Customer ID` (with a space) |
| "StockCode: 5-digit" | also `85123A`, `POST`, `DOT`, `M`, `BANK CHARGES`, `AMAZONFEE` ... |
| "InvoiceNo: 6-digit, 'c' = cancellation" | upper-case `C`, plus 6 invoices starting with `A` |
| (nothing) | the two sheets **overlap** in December 2010 |

**Metadata that doesn't match the data makes reuse risky.** That is exactly what the "R" in FAIR is about.

**Theory, metadata types (Ch. 1):**
- **descriptive:** title, keywords;
- **structural:** files, columns, units;
- **administrative:** licence, version, access.

### 3.4 Licence check
- **CC BY 4.0** allows sharing and changing, also commercially, **if** we credit the source, link the licence and say what we changed.
- GeoNames is CC BY 4.0 too, so combining both is allowed.
- Our `metadata.json` has `creditText`, `license` and `isBasedOn` for both sources.

---

## 4. Profiling (slide 4)

**Theory (Ch. 2):**
- **Profiling** = examining the data **before** changing it: structure, patterns, mistakes. It is the diagnosis before the treatment.
- **Column analysis** looks at each column alone: type, missing values, cardinality (number of distinct values), min/max, distribution.
- **Structure analysis** looks at relationships: keys, functional dependencies, inclusion dependencies.
- The result is a **cleaning plan**.

**What:** `profiling/profile_raw.py` reads the raw files **without changing them** and writes `reports/profiling.md`, `reports/profiling_*.csv` and four charts.
**Why a script:** so the numbers are exact and repeatable, and the same KPIs can be compared after cleaning.
**In Tableau Prep:** the **profile pane** of every Clean step shows the same column profiles visually. Use it for screenshots.

### 4.1 Size
| table | rows | columns |
|---|---|---|
| sheet Year 2009-2010 | 525,461 | 8 |
| sheet Year 2010-2011 | 541,910 | 8 |
| **sales total** | **1,067,371** | 8 |
| countryInfo.txt | 252 countries + **50 comment lines** at the top | 19 |

Period: 2009-12-01 07:45 to 2011-12-09 12:50. Distinct: 53,628 invoices, 5,305 product codes, 5,942 customers, 43 countries.

### 4.2 The six quality dimensions, one real example each
| Dimension | Meaning | Real example in this data |
|---|---|---|
| **Accuracy** | data matches reality | the most expensive "item" (38,970 GBP) is not a product but a manual correction (`M`, "Manual"); some descriptions are stock notes, not product names (`10133`: "damaged", `10080`: "check") |
| **Completeness** | required data present | **22.8% of lines have no Customer ID**; 4,382 lines have no description |
| **Consistency** | no conflicts | product `15058A` is called both "BLUE WHITE SPOTS GARDEN PARASOL" and "BLUE POLKADOT GARDEN PARASOL"; customer 12413 appears with Spain and France (13 customers have 2 countries) |
| **Timeliness** | up to date | the data ends on **2011-12-09**: fine for history, too old for a live model |
| **Uniqueness** | each record once | **34,335 identical lines**, 23,221 of them because December 2010 is in **both** sheets |
| **Validity** | follows rules and formats | 6,207 prices ≤ 0; 6 invoices start with "A" ("Adjust bad debt", price −53,594 GBP); "EIRE" and "RSA" are not standard country names |

### 4.3 Quality KPIs of the raw data
**Theory:** a KPI makes a dimension measurable as one number, so it can be compared **before and after**:
- completeness = filled ÷ all fields;
- duplication = duplicates ÷ rows;
- validity = passing ÷ checked.

| KPI (raw) | value |
|---|---|
| Completeness, all 8 columns | **97.10%** |
| Completeness of Customer ID | **77.23%** |
| Duplication (identical lines) | **3.22%** (34,335 lines) |
| Validity (7 rules) | **99.78%** |
| Timeliness: last sale | 2011-12-09 |

**The validity rules** were written *before* cleaning ("define rules first", Ch. 2):

| Rule | Failing lines (raw) |
|---|---|
| R1 invoice = 6 digits (optionally C) | 6 |
| R2 description present | 4,382 |
| R3 unit price > 0 | 6,207 |
| R4 quantity > 0 on a sale | 3,457 |
| R5 date inside 2009-12-01 to 2011-12-31 | 0 |
| R6 a cancellation has a negative quantity | 1 |
| country is a real country | 2,535 |

### 4.4 Column analysis
`reports/profiling_column_profile.csv` and chart `profile_missing_values.png`:
- **Customer ID:** 22.8% missing, the biggest gap. These are guest orders, so the *sale* is real and only the customer is unknown.
- **Description:** 0.41% missing, mostly on lines with price 0 (stock corrections, not sales).
- **StockCode:** 5,305 distinct, but not all are products: `POST` (1,893 lines), `DOT` (1,443), `M` (883), `C2`, `ADJUST`, `BANK CHARGES` ... (chart `profile_non_product_codes.png`).
- **Price:** median 2.10 GBP for products; maximum **38,970 GBP**, which is a cancelled manual correction (`C556445`, code `M`), not a product.
- **Invoice:** text, because of the "C" and "A" prefixes. A tool that guesses "number" would destroy the cancellations. In Tableau Prep we set the type to **string** on purpose.

### 4.5 Structure analysis
**Theory:**
- A **key** identifies a row.
- A **functional dependency (FD)** A → B means one A always has the same B.
- An **inclusion dependency** means every value in one table exists in the other (no orphans).

| Check | Result | Evidence |
|---|---|---|
| Is `Invoice + StockCode` a unique key? | **no** | 88,585 lines share invoice and product (the same item twice on one invoice), so a line has no natural key |
| FD `StockCode → Description` | **violated** | 1,232 of 4,950 products have more than one description |
| FD `Customer ID → Country` | **violated** | 13 customers appear with two countries |
| Overlap between the two sheets | **yes** | **23,221** identical lines in both (December 2010), chart `profile_lines_per_month.png` |
| Inclusion: `Country` ⊆ reference countries | **violated** | EIRE (17,866), Netherlands (5,140; GeoNames says "The Netherlands"), Channel Islands, Unspecified, USA, RSA, Korea, European Community, West Indies, Czech Republic |
| Reference table clean? | **no** | 50 comment lines starting with `#` before the data |

### 4.6 Distribution and outliers: the IQR rule
**Theory (Ch. 2, the professor's slide):**
1. Q1 and Q3 are the 25% and 75% points of the sorted values.
2. IQR = Q3 − Q1.
3. Fences = Q1 − 1.5·IQR and Q3 + 1.5·IQR.
4. Values outside the fences are outliers.

Quartiles ignore extremes. **"A rule flags, a human decides."**

**Result on all product prices:** Q1 = 1.25 GBP, Q3 = 4.13 GBP, IQR = 2.88, upper fence **8.45 GBP**. That puts **77,599 lines** "above the fence", but most are simply expensive products (a cabinet costs more than a pencil).

**Conclusion:** one global fence is wrong for a shop with thousands of different products. We must compare each price **with the usual price of the same product**. How we do that, and why plain IQR still isn't enough, is in 6.3.

### 4.7 The cleaning plan (output of profiling, input for the flow)
| # | Issue | Lines | What the flow does |
|---|---|---|---|
| 1 | identical lines (incl. the December 2010 overlap) | 34,335 | Aggregate on all columns: keep one, count `copies` |
| 2 | Customer ID missing | 243,007 | keep for revenue; exclude from customer features (`has_customer`) |
| 3 | cancellations (invoice C...) | 19,494 | own output: a real business event, not an error |
| 4 | postage, fees, manual codes in StockCode | 4,884 | own output `non_product` |
| 5 | price 0 or negative | 6,207 | quarantine (rule R3) |
| 6 | missing description | 4,382 | quarantine (rule R2) |
| 7 | products with several descriptions | 1,232 | `dim_product`: the most used description |
| 8 | non-standard country names | 26,338 | CASE mapping in Prep, then join the reference table |
| 9 | extreme prices (max 38,970 GBP) | - | flag per product (IQR + 3× median), keep |
| 10 | text: double spaces, trailing spaces, mixed case | - | TRIM, one space, UPPER |

---

## 5. Cleaning and transformation in Tableau Prep (slides 5, 5-6 slides)

**The flow:** `prep/online_retail_flow.tfl`
- 34 steps;
- it opens in Tableau Prep Builder (verified in the app's own logs: no errors);
- it runs in about **1.5 minutes**.

**Theory (Ch. 2 + Tableau Prep lecture):** cleaning has seven habits:
1. understand the data;
2. define rules first;
3. keep raw unchanged;
4. clean step by step;
5. validate (count rows!);
6. log every decision;
7. prepare for reuse.

Tableau Prep supports all of them. Every Clean step has a **Changes pane** listing every change, which is the cleaning log. Every step shows its rows, so we can check row counts after each one.

### 5.1 The full flow (slide: "the full flow")
```
1a Input sales 2009-2010 ─┐
                          ├─ 2 Union ─ 3 Clean names/types/text ─ 4 Aggregate remove duplicates ─ 5 Clean calculated fields ─ 6 SCRIPT quality rules ─┐
1b Input sales 2010-2011 ─┘                                                                                                                         │
1c Input countries ─ 7 Clean countries (reference) ────────────────────────────────────────────────────────────────────────────────────────────── 8 Join (left)
                                                                                                                                                    │
                                                                                                                                            9 Clean final fields
                                                       ┌──────────────────────────────┬──────────────────────────┬────────────────────────┬────────┘
                                         10a trusted sales                    10b quarantine           10c cancellations        10d non-product
                   ┌───────────┬────────────┼───────────────┬───────────────┐       │                        │                       │
            fact_sales.csv  fact_sales  11 Aggregate     12 Clean with     15-17 one         quarantine_lines.csv     cancellations.csv     non_product_lines.csv
                            .hyper      monthly revenue  a customer        description
                                            │                 │             per product
                                   monthly_revenue.csv  13 Aggregate per customer ─ 13b round ─ 14 SCRIPT RFM ─ customer_features.csv
                                                                                                               dim_product.csv
```
Every arrow is a real connection in the flow file. The step numbers are part of the step names, so you can find each one in Tableau Prep.

### 5.2 Steps 1a-1c: Input (Extract)
**What:** three Input steps.
- **1a** and **1b** read the two sheets of `online_retail_II.xlsx` with Tableau's Excel connector.
- **1c** reads `countryInfo.txt` as a text file with a **tab** separator and **no header row**, because its header line also starts with `#`.

**Why:** Extract is the first ETL step. We read the files *exactly as downloaded*. No other program converts or touches them.

**How (in Tableau Prep):**
- Connections › + › Microsoft Excel → choose the sheet.
- Connections › + › Text file → in the Input pane set "Field separator: Tab" and untick "First line contains header" (columns are then called F1 ... F19).
- **Check the detected data types, and correct one.** Tableau Prep looks at the values and *guesses* each column's type:
  - Quantity = whole number, Price = decimal, InvoiceDate = date & time, StockCode = text, Customer ID = whole number (made text in step 3);
  - **Invoice = whole number**, because almost all invoices are 6 digits. **That guess is wrong.** Read as a number, `C489449` cannot be a number and would silently become empty, so all 19,494 cancellations would lose their "C".
  - So in the Input step we click the type icon of **Invoice** and change it to **String**. Prep records this as a *Change type* action on the Input step, and it then reads the column as text from the start.

**Theory (Tableau Prep lecture, "check before you clean"):** is row 1 the header? Which separator? Did Prep guess the types right? Here the wrong guess was real. We found it when the Tableau Prep app re-detected the types and every formula using `[invoice]` failed.

**Result:** 525,461 + 541,910 sales rows; 302 lines in the country file.

### 5.3 Step 2: Union (stack both years)
**What:** the two sheet inputs are dropped onto one Union step.

**Why:**
- Revenue per month across **both** years needs **one** table.
- Both sheets have the same 8 columns, so they stack.

**How:**
- Drag input 1b onto input 1a › "Union".
- Prep shows "mismatched fields: **0**".
- Prep adds the field **Table Names** = which sheet a row came from (e.g. `online_retail_II.xlsx/Year 2010-2011`). We keep it as `source_sheet`: **row-level lineage**.

**Theory (Ch. 2):**
- A union adds rows; rows out ≈ sum of rows in.
- Risk: **schema drift** (renamed or missing columns). That's why we check "mismatched fields".
- Union ≠ join: a join adds columns.

**Result:** 525,461 + 541,910 = **1,067,371 rows**. This still *includes* the December 2010 overlap. Step 4 removes it.

### 5.4 Step 3: Clean: names, types, text (15 changes)
**What and why, line by line (each line = one entry in the Changes pane):**

| Change | Why |
|---|---|
| rename Table Names → `source_sheet` | lineage with a readable name |
| rename Invoice → `invoice`, StockCode → `stock_code`, Description → `description`, Quantity → `quantity`, InvoiceDate → `invoice_datetime`, Price → `unit_price_gbp`, Country → `country_raw` | **names are metadata** (Tableau lecture): one naming style, and the **unit (GBP) is in the name** so nobody guesses the currency |
| `invoice = UPPER(TRIM([invoice]))` | remove invisible spaces; one letter case |
| `stock_code = UPPER(TRIM([stock_code]))` | same; `85123a` and `85123A` become one product |
| `description = UPPER(TRIM(REGEXP_REPLACE([description], '\s+', ' ')))` | "LUNCH BAG  BLACK SKULL." (two spaces) and "lunch bag black skull." become **one** spelling: **consistency** |
| `customer_id = STR([customer_id_raw])` | Prep reads customer 13085 as a number, but an ID is a **label, not a number**, so it becomes the text "13085" (nobody should add up customer IDs); an empty ID stays empty |
| `country = CASE ... END` | EIRE → Ireland, Netherlands → The Netherlands, USA → United States, RSA → South Africa, Korea → South Korea, Czech Republic → Czechia, Unspecified → empty. **Consistency + accuracy:** one official name per country, and the names now match the reference table for the join in step 8 |

**How in the GUI:**
- double-click a column name to rename it;
- the column menu › Clean › Trim spaces / Make uppercase;
- "Create Calculated Field" for the formulas.

**Result:** same 1,067,371 rows. **Cleaning a value never deletes a row.**

### 5.5 Step 4: Aggregate: remove duplicate rows
**What:** an Aggregate step that **groups by all 9 business columns** (invoice, stock code, description, quantity, date-time, price, customer, country_raw, country). It keeps:
- `MIN(source_sheet)` as lineage: the sheet of the first copy;
- `COUNT(invoice)` as **`copies`**: how many identical lines became this one row.

**Why:**
- **Uniqueness:** 34,335 lines are exact copies.
- 23,221 of them are the December 2010 overlap. Without this step, December 2010 revenue would be **counted twice**.
- The rest are the same line entered twice in the shop system.
- **Why group by *after* step 3:** "LUNCH BAG  BLACK" and "lunch bag black" are only seen as identical *after* the text was standardised.
- **Why keep `copies`:** nothing disappears silently. Later we prove that the sum of `copies` equals the raw row count (6.6).

**How:**
- Add an Aggregate step, drag the 9 columns to "Grouped fields", and set the aggregations (MIN, COUNT).
- This is the standard Tableau Prep way to remove duplicates.

**Theory (Ch. 2, "uniqueness"; Tableau lecture "identify duplicate rows").** For the overlap, `MIN(source_sheet)` = the 2009-2010 sheet is kept as the origin. The "new data" test relies on this (6.6).

**Result:** 1,067,371 → **1,033,036 rows** (−34,335).

### 5.6 Step 5: Clean: calculated fields (6 changes)
| Field | Formula | Why |
|---|---|---|
| `invoice_date` | `DATE([invoice_datetime])` | day without time, for daily reports |
| `invoice_month` | `DATE(DATETRUNC('month', [invoice_datetime]))` | first day of the month, so monthly revenue is one group per month |
| `is_cancellation` | `STARTSWITH([invoice], "C")` | UCI's rule: "C" = cancelled |
| `line_type` | product if the stock code starts with 5 digits, `cancellation` if C, else `non_product` | separates real products from POST, DOT, M, BANK CHARGES ... so postage is not counted as product revenue |
| `line_revenue_gbp` | `ROUND([quantity] * [unit_price_gbp], 2)` | revenue per line, **rounded to pence** (why rounding matters: 6.6) |
| `has_customer` | `NOT ISNULL([customer_id])` | lines without a customer still count for revenue, but not for customer features |

**Theory:** transformation = creating features (Ch. 2: "create features", binning); format standardisation.

### 5.7 Step 6: Script step 1: quality rules in Python
**What:** a **Script step** connected to TabPy runs the function `apply_quality_rules` from `prep/script_quality_rules.py`. It adds three columns:
- `dq_status` = trusted / quarantine / cancellation / non_product;
- `dq_reason` = the first broken rule;
- `price_outlier_iqr`.

**Why a Script step, not more calculated fields:**
- The rules are the heart of "can this data be trusted", so they must be **code**.
- Code is versioned in Git, **unit-tested on its own** (`tests/`), and gives the identical answer on every run. This is exactly the exam's "Python functions run inside Tableau Prep's Script step".
- The per-product price rule needs grouping and quartiles per product, which Python does in a few clear lines.

**How:**
- Add Step › Script.
- Connection type: Tableau Python (TabPy) Server.
- File: `prep/script_quality_rules.py`.
- Function name: `apply_quality_rules`.
- The file's `get_output_schema()` tells Prep every output column and its type.

The rules themselves are explained in section 6.2.

**Result:** 1,033,036 rows in, 1,033,036 out (rows are only *labelled*, never dropped):

| dq_status | rows |
|---|---|
| trusted | **1,003,214** |
| cancellation | 19,103 |
| quarantine | 6,021 |
| non_product | 4,698 |

### 5.8 Step 7: Clean: countries (the reference table, 9 changes)
| Change | Why |
|---|---|
| keep only rows where `NOT STARTSWITH([F1], "#")` | the file starts with 50 comment lines; **reference data needs cleaning too** |
| rename F1 → `iso2`, F2 → `iso3`, F5 → `country_name`, F8 → `population`, F9 → `continent_code` | readable names |
| remove the other 14 columns | we only need what we use (minimisation) |
| population → whole number | correct type |
| `continent` = CASE EU → Europe, AS → Asia, ... | readable continent names |

**Result:** 252 countries, 7 columns.

### 5.9 Step 8: Join: add country data (left join)
**What:** sales (left) **LEFT JOIN** countries (right) on `country = country_name`.

**Why:**
- It adds ISO codes, continent and population to every line. Now revenue can be compared by continent, and other datasets (which use ISO codes) can be joined later: **interoperability**.
- Why **left:** every sales line must stay, even if its "country" is not a real country. An **inner** join would silently delete the 2,403 trusted lines from "Channel Islands", "Unspecified", "European Community" and "West Indies".

**How:** drag the countries step onto the sales step › Join › join clause `country = country_name` › click the left circle of the Venn diagram (left join).

**Theory (Ch. 2, Tableau lecture "check the row count after every join"):**
- duplicate keys on the right side would multiply rows;
- missing keys produce nulls.
- Our right side has unique country names, so rows in = rows out.

**Result:** 1,033,036 → **1,033,036** rows. 2,403 trusted lines have no match → `country_matched = false` (step 9).

### 5.10 Step 9: Clean: final fields
- Remove `country_name` (the right-hand join key is a copy of `country`).
- `country_matched = NOT ISNULL([iso3])`. Why: an explicit flag says "this is not a real country", instead of leaving an unexplained null.

### 5.11 Steps 10a-10d: split by quality status
**What:** four Clean steps, each with one filter `[dq_status] = "..."`. Each feeds its own output.

**Why:**
- The professor's rule: **"never a silent bad number"**.
- Bad lines are not deleted: they go to `quarantine_lines.csv` *with their reason*.
- Cancellations and postage are not errors, but they are not product sales, so they get their own tables.
- A manager can look at each file and question every decision.

**Result:**

| output | rows | `copies` (raw lines behind them) |
|---|---|---|
| fact_sales | 1,003,214 | 1,036,877 |
| quarantine_lines | 6,021 | 6,209 |
| cancellations | 19,103 | 19,493 |
| non_product_lines | 4,698 | 4,792 |
| **total** | **1,033,036** | **1,067,371 = the raw total** |

### 5.12 Steps 11-17: aggregates and outputs
| Step | What | Why |
|---|---|---|
| **11 Aggregate: monthly revenue** | group by month, country, continent: SUM revenue, COUNTD invoices, SUM units, COUNTD customers | the OLAP answer for the managers (562 rows) |
| **12 Clean: sales with a customer** | keep `has_customer` | customer features need a customer |
| **13 Aggregate: one row per customer** | MIN country, MIN/MAX date, COUNTD invoices, COUNT lines, COUNTD products, SUM revenue | change granularity from *line* to *customer* (5,852 rows) |
| **13b Clean: round money** | `ROUND([revenue_gbp], 2)` | sums of prices are not exact in a computer (6.6) |
| **14 Script step 2: RFM features** | Python `rfm_features`: recency, scores 1-5, segment | the AI-ready customer table (6.4) |
| **15-17 one description per product** | count lines per (product, description) → `{FIXED [stock_code] : MAX(...)}` → keep the most used → one row per product | fixes the broken FD `StockCode → Description` (4,707 products) |
| **Export: ISO dates** (3 steps) | `STR([date])` → `2011-04-18` | otherwise Prep writes dates in the computer's language format (`18/04/2011`), which differs between computers; ISO is the same everywhere (reproducibility + interoperability) |
| **Outputs** | 7 CSV files + `fact_sales.hyper` | **Load**: CSV for any tool, Hyper as the warehouse for Tableau |

**Why one description per product:**
- Profiling found 1,232 products with several names in the raw data. After step 3's text standardisation and the removal of quarantined lines, **599 products still have 2-4 names**.
- A product dimension must have **one** name per product: the functional dependency must hold.
- We choose the **most used** description, an explainable rule. Ties go to the alphabetically first.

**Theory, the LOD expression:**
- `{FIXED [stock_code] : MAX([lines_with_description])}` computes one value per product and writes it on every row of that product.
- Prep allows such an expression only **on its own** in a calculated field. That is why it is a separate field.

---

## 6. Reproducible pipeline: Python inside Tableau Prep's Script steps (slide 6)

### 6.1 What "reproducible pipeline" means, and how our flow is one
**Theory (Ch. 3):**
- A reproducible pipeline gives the **same output from the same input**, every time and on every computer.
- It shows **where every number came from**.
- Four things must stay the same: the raw data, the code, the rules, the software versions.
- A notebook clicked by hand fails this: cells run out of order, and some are forgotten.

**How our project meets it:**

| Requirement | How |
|---|---|
| same raw data | `data/raw/` is never written; SHA-256 checksums in `_download_manifest.json` prove it |
| same steps, fixed order | the **flow file** is the pipeline: 34 steps that always run in the same order, with **one click** (Run Flow) or **one command** (`tools/run_flow.sh prep/online_retail_flow.tfl`) |
| same rules | the rules are **Python functions** in `prep/script_*.py`, called by the Script steps, kept in Git |
| same software | Tableau Prep Builder 2026.2; Python 3.12 with pinned versions in `requirements.txt`; TabPy settings in `tools/tabpy.conf` |
| proof | reconciliation, fingerprints of two runs, "new data" test, unit tests (6.6) |

### 6.2 Script step 1: the quality rules (`prep/script_quality_rules.py`)
**Why rules as functions (Ch. 3, "one rule = one function = one place to fix"):**
- If the price rule were copied into three places, a fix would miss one.
- As a function, it lives once.
- It is **tested on its own** with three hand-made rows before it touches a million real ones.
- Tableau Prep and the tests call the **same** function.

**The functions, one job each:**

| Function | What it does | Why |
|---|---|---|
| `to_datetime(values)` | turns Prep's date text `2010-12-01T08:26:00Z[UTC]` into a real date | Tableau Prep sends dates in Java format; the `[UTC]` label must be removed first (we found this when every row failed rule R5 on the first run) |
| `quality_reason(df)` | returns the **first** broken rule per row, or nothing | one clear reason per row; "first match wins" keeps the reasons countable |
| `price_outlier_flag(df)` | flags suspicious prices per product (6.3) | outliers are **flagged, not deleted** |
| `classify(df)` | combines the reason and the line type into `dq_status` | one status per line: trusted / quarantine / cancellation / non_product |
| `apply_quality_rules(df)` | **the function Tableau Prep calls**: adds dq_status, dq_reason, price_outlier_iqr; never drops a row | splitting happens visibly in Prep (steps 10a-10d) |
| `write_run_log(...)` | appends one line to `logs/pipeline_run_log.txt` | evidence of every run (when, how many rows, which statuses) |
| `get_output_schema()` | lists every output column with its Tableau type | Tableau Prep requires it to know the Script step's output |

**The six rules (in this order, the first broken one is reported):**

| Rule | Check | Dimension | Example caught |
|---|---|---|---|
| R1 | invoice is 6 digits, optionally with a C in front | validity | `A506401` "Adjust bad debt", price −53,594 GBP |
| R2 | description not empty | completeness | 4,275 lines, mostly price 0 stock corrections |
| R3 | unit price > 0 | validity | 1,739 lines with price 0 (samples, damaged goods, corrections) |
| R4 | quantity > 0 on a sale | validity | (all such lines also had price 0, so R3 reported them first) |
| R5 | date between 2009-12-01 and 2011-12-31 | validity / timeliness | 0 lines: the rule exists to protect against future files |
| R6 | a cancellation has a negative quantity | consistency | 1 line |

**Quarantine result:** R2 4,275 · R3 1,739 · R1 6 · R6 1 = **6,021** lines, each with its reason.

**Why the order matters:** a line without a description and with price 0 breaks R2 *and* R3. Reporting only the first keeps every line in exactly one reason group, so the numbers add up.

### 6.3 The price-outlier rule: why "IQR + 3× median"
**What:** a price is flagged when it is **both**
- (a) outside the IQR fence of **the same product's** prices, **and**
- (b) at least **3 times** that product's median price, or at most a third of it.

Only products with at least 10 lines are judged.

**Why, step by step:**
1. **A global IQR fence** (8.45 GBP) flags 77,599 lines, mostly normal expensive products. Wrong level of comparison.
2. **IQR per product** is better, but it still flagged **149,370 lines (15%)**. Why: this is a wholesale shop, and one product is sold at a few **quantity-discount prices**. Most products have one dominant price, so their IQR is **0**, and *any* other price, even a normal 10% discount, lands outside the fence.
3. **IQR per product + at least 3× (or ⅓ of) the median** keeps only real anomalies: **6,368 lines (0.6%)**, e.g. a car flag at 1,157 GBP whose usual price is 0.42 GBP.

**The lesson for the presentation:** the lecture's rule is the right *idea*, but it must fit the *data*. We tested three versions and chose the one whose flags a human would agree with. Flagged lines stay in the trusted table ("a rule flags, a human decides").

### 6.4 Script step 2: AI-ready customer features (`prep/script_rfm_features.py`)
**What:** `rfm_features(df)` receives one row per customer (built in Prep's step 13) and adds:

| Feature | Meaning | Why it predicts buying again |
|---|---|---|
| **R**ecency `recency_days` | days from the last purchase to 2011-12-10 (the day after the last sale) | customers who bought recently are more likely to buy again |
| **F**requency `invoices` | number of different orders | regular buyers come back |
| **M**onetary `revenue_gbp` | total spent | high spenders are worth keeping |
| `r_score`, `f_score`, `m_score` | 1-5 by **quintiles** (each score holds 20% of customers); 5 = best | puts all three on the same 1-5 scale (like scaling in Ch. 2) |
| `rfm_score` | e.g. 555 = best | one sortable code |
| `segment` | Champions (R≥4, F≥4), Loyal (R≥3, F≥4), New or promising (R≥4, F≤2), At risk (R≤2, F≥3), Lost (R≤2, F≤2), otherwise Needs attention | a name the managers understand |

**Why RFM:** it is the standard, explainable customer model in e-commerce. It only needs data we really have (dates, invoices, money). It is a typical **input for machine learning**: a classifier "will buy again?" or clustering.

**Two details that make it reproducible:**
- **Ties:** many customers have the same values (e.g. exactly 1 invoice). Quintiles need an order, so we rank with `method="first"`, and we **sort by customer ID first**. Without sorting, Prep's random row order changed the segment counts between runs. Our reproducibility check found this (6.6).
- **Empty call:** Tableau Prep first calls the Script step with **no rows** to check it. The function returns the right columns for an empty table instead of crashing.

**Result:** 5,852 customers → Champions 1,464 · Lost 1,511 · Needs attention 1,084 · At risk 830 · Loyal 517 · New or promising 446.

### 6.5 The functions run on their own: unit tests
**What:** `tests/test_pipeline_functions.py`, 8 tests, run with `.venv/bin/python -m pytest tests`. **Result: 8 passed.**

| Test | Checks |
|---|---|
| Tableau date format | `2010-09-14T16:25:00Z[UTC]` is read correctly |
| each rule gives its reason | 9 hand-made lines → exactly R1 ... R6, trusted, cancellation, non_product |
| first broken rule wins | a line breaking R2 and R3 is reported as R2 |
| price outlier needs IQR **and** 3× median | a 2.5 GBP discount tier is *not* flagged, a 40 GBP anomaly *is* |
| small products not judged | a product with 3 lines is never flagged |
| RFM scores and segments | the best customer = Champions, an old one-time buyer = Lost |
| RFM independent of row order | shuffled input → identical scores |
| empty input from Prep's check | no crash |

**Why:** this is the exam's "Python functions run **on their own**". It is also the fastest way to prove a rule before it runs on a million lines.

### 6.6 Proof: same input → same output; new data → same rules
**1. Reconciliation (`tools/verify_outputs.py` → `reports/verification.md`):**
raw 1,067,371 lines = trusted 1,036,877 + quarantine 6,209 + cancellations 19,493 + non-product 4,792 (counted with `copies`).
**Balanced: yes.** Not a single line disappeared without a trace.

**2. Test 1: the same flow on the same data, twice (`tools/check_reproducibility.py`):**
- The script fingerprints every output: the SHA-256 of all rows **sorted**, because Prep writes rows in any order.
- **Result: all 7 outputs identical.**

  It did not pass at first. The check found **two real reproducibility bugs**:

  | Bug | Cause | Fix |
  |---|---|---|
  | RFM segments differed (e.g. Lost 1,509 vs 1,522) | Prep sends rows in a different order each run; ties in the ranking were broken by that order | sort by customer ID before ranking |
  | monthly revenue differed (`8768.27` vs `8768.270000000`) | a computer adds decimals inexactly, and the tiny error depends on the **order of adding** | round money to pence in Prep (`ROUND(..., 2)`) |

  **Why this matters:** without the check, two runs would have produced slightly different reports, and nobody would know why. The check is the reproducibility proof the exam asks for.

**3. Test 2: new data arrives:**
- The same flow is built a second time with **only** the 2009-2010 sheet (`prep/online_retail_flow_first_year_only.tfl`), as if 2010-2011 had not arrived yet. Then the full flow runs with both years.
- **Result:** all **518,596** lines of 2009-2010 get **exactly the same decision** in both runs: 502,322 trusted, 3,685 quarantine, 10,181 cancellations, 2,408 non-product.
- The rules don't change when new data is added. This is "re-run on new data with the same result".

### 6.7 Failing safely, logging, versioning
- **Single bad rows → quarantine with a reason** (6,021 lines), never silently deleted.
- **Whole-run problems → the run fails and says where.** We saw this ourselves:
  - TabPy refused 232 MB → "Unable to connect to TabPy";
  - a wrong date format → every row failed R5, visible at once in the run log;
  - a missing column → Tableau Prep reports "unknown field" at the step.
- After every run, `verify_outputs.py` checks the reconciliation. An incomplete run would show "balanced: NO".
- **Run log:** `logs/pipeline_run_log.txt` gets one line per Script step per run (time, rows, counts).
- **Versioning:**
  - the flow file and the Python rules are text, ready for Git (commit, review, pull request, Ch. 3);
  - raw data has checksums;
  - each output has a fingerprint in `data/output/_manifest.json`;
  - the dataset version is 1.0.0.

### 6.8 Quality KPIs before → after
| KPI | Raw (before) | Trusted fact table (after) |
|---|---|---|
| Completeness of core fields | 97.10% (8 columns) | **99.99%** (only "Unspecified" countries are empty) |
| Duplication | 3.22% | **0%** |
| Validity (rules) | 99.78% | **100%** |
| Lines with a customer | 77.23% | 77.41% |

**Why "lines with a customer" barely moves, and why that is right:** a missing customer cannot be invented. Guest orders are real sales, so they stay in the revenue. They are only excluded where a customer is needed (RFM). Honest KPIs show what cleaning **cannot** fix.

---

## 7. Governance (slide 7)

**Theory (Ch. 4):** governance turns individual good practice into an organisation-wide guarantee. *"A model is only as trustworthy as the governance behind the data it was trained on."* The exam asks for **roles, lineage, data dictionary, AI risks**. Everything is in `governance/`.

### 7.1 Roles
| Role | Who (shop / project) | Example here |
|---|---|---|
| **Data Owner**: decides, accountable | Head of Sales / group lead (TO CONFIRM) | approves version 1.0.0; decides that cancellations are kept, not deleted |
| **Data Steward**: quality and documentation | sales analyst / member (TO CONFIRM) | owns rules R1-R6 and the outlier rule; maintains the data dictionary |
| **Data Custodian**: runs the technology | data engineer / member (TO CONFIRM) | runs the flow and TabPy; keeps `data/raw` read-only |
| **Governance Manager**: sets policies | data-protection officer / course rules + GDPR | "raw data is never changed" |
| **Data Consumer**: uses, reports problems | managers, data scientist | reported "1,232 products have several names" → steward built `dim_product` |

**Why named roles:** "If everyone owns it, nobody does." The loop: consumer reports → steward fixes → owner approves → custodian re-runs.

### 7.2 Lineage (the metro map) and provenance (the passport)
- **Lineage diagram:** `governance/GOVERNANCE.md`. Sources → raw zone → flow steps → outputs → dashboard / model.
- **Row-level lineage:** every output row carries:
  - `source_sheet` (which workbook sheet it came from);
  - `copies` (how many identical raw lines it represents).

  Together with the business columns (invoice, product, date), every row can be found again in the Excel file.
- **Upstream (root cause):** strange November revenue → `monthly_revenue` → `fact_sales` (filter Nov) → `source_sheet` + invoice → the raw line.
- *Why not a row number?* Prep's automatic "Source Row Number" exists in the command-line run but not in the app, and a flow must behave the same in both, so we don't use it.
- **Downstream (impact):** if UCI renamed `Price`, the flow fails at step 3, so no dashboard is fed wrong data.
- **Provenance per release:** source checksums + flow version + software + run time + output fingerprints.

### 7.3 Data dictionary
`governance/data_dictionary.md` has every column of every output: meaning, type/unit, rule, source (raw / ref / derived / script).

**Why:** without it, "Price" is ambiguous (which currency? per item or per line?). We put the unit **in the column name** (`unit_price_gbp`) **and** in the dictionary.

### 7.4 Classification, protection and the TabPy security decision
- **Confidential:** raw data and `fact_sales` / `customer_features`. Customer IDs are pseudonymous numbers, but an ID plus country plus purchases can still identify a small business or person, so under GDPR it is still personal data.
- **Internal:** `monthly_revenue`, `dim_product`.
- **Public** (after owner approval): charts and aggregates.

**The TabPy decision:**
- TabPy without a password runs **any** Python code it receives. If it listened on the network, anyone in the same Wi-Fi could run programs on this computer.
- TabPy has no "localhost only" setting, so `tools/run_tabpy_local.py` forces it to listen only on 127.0.0.1.
- This is a **governance decision**, not just a technical one: protection measures (Ch. 4: access control).

### 7.5 Data contract
`governance/fact_sales.contract.yaml` (ODCS style) covers:
- schema, units and rules;
- the owner;
- update frequency;
- change notice: 14 days before a breaking change.

**Why:** a model breaks silently if a column is renamed. A contract makes changes announced, not surprising.

### 7.6 AI risks
| Risk | In our data | Control |
|---|---|---|
| missing customers | 22.6% of trusted lines (13.1% of revenue) have no customer | `has_customer` flag; segments only for known customers; documented |
| country bias | UK = 85.5% of revenue | evaluate a model per country |
| outdated data / drift | 2009-2011, before COVID | stated limitation; re-train on new data |
| seasonality | November peak | reference date documented |
| ties in scores | many one-time buyers | deterministic tie-break, documented |
| wrong values | 38,970 GBP manual lines, cancellations | quarantine, IQR flag, separate tables |
| re-identification | customer ID + country + purchases | aggregate use only (contract), confidential |
| regulation | EU AI Act Art. 10: training data must be relevant, representative, as error-free and complete as possible, with documented governance | this documentation is that evidence |

### 7.7 AI-ready checklist
| Question | Answer |
|---|---|
| Documented? | yes: dictionary, contract, roles |
| Tested? | yes: rules on every run, KPIs, 8 unit tests |
| Versioned? | yes: checksums, flow + code in Git, identical fingerprints |
| Traceable? | yes: source_sheet / copies, lineage diagram, the flow file |
| Governed? | partly: roles defined, names TO CONFIRM, no real access system |

---

## 8. Conclusion (slide 8)

### 8.1 Answer to the problem statement
**Revenue** (`monthly_revenue.csv`, trusted lines):
- **19.64 million GBP** over 25 months (Dec 2009 to 9 Dec 2011). 2010: 9.37 M, 2011: 9.47 M; December 2009 alone: 0.80 M.
- Strong **Christmas season**: the best months are **November 2011 (1.45 M)** and **November 2010 (1.43 M)**. The shop should plan stock and staff for September to November.
- **United Kingdom = 85.5%** of revenue, then Ireland 3.2%, the Netherlands 2.8%, Germany 1.9%, France 1.6%. Europe = 98.2%.
- Cancellations were worth −1.46 M GBP (kept in their own table).

**Customers** (`customer_features.csv`, 5,852 customers):
- **Champions** (1,464 customers, 25%) bring **69% of the revenue**: median 10 orders, last purchase 17 days ago. **Keep them.**
- **At risk** (830) used to buy often (median 4 orders) but not for a year (median 374 days), 9% of revenue. **Win them back now.**
- **Lost** (1,511): one order, long ago, 3.6% of revenue.
- The top 20% of customers bring 77% of the revenue: the 80/20 rule.

### 8.2 Can the data be trusted, reused and fed into AI, and how do we prove it?
| Claim | Proof |
|---|---|
| **Trusted** | six dimensions profiled; rules R1-R6 run on every line; 1,067,371 = trusted + quarantine + cancellations + non-product + duplicates (balanced); trusted table 99.99% complete, 100% valid, 0% duplicates |
| **Reused** | FAIR 6/8 → 8/8 with a DOI; schema.org metadata; CC BY 4.0 with credit; data dictionary; ISO dates and codes |
| **Fed into AI** | `customer_features.csv` (RFM, scaled 1-5, segments); AI risks documented; AI-ready checklist 4.5 / 5 |
| **Reproducible** | one flow, one click; identical fingerprints on re-run; identical decisions on new data; 8 unit tests |

**Answer:** **yes, within documented limits**:
- 22.6% of lines have no customer;
- the UK dominates;
- the data ends in 2011;
- 599 products had to get one chosen name.

### 8.3 Lessons learned
1. **Profile before you clean.** The overlap of the two sheets was invisible until we counted lines per month and sheet. Without that, December 2010 revenue would have been doubled.
2. **Not every "bad" row is an error.** Cancellations and postage are real events, so they get their own tables, not the bin.
3. **Textbook rules must fit the data.** Plain IQR flagged 15% of a wholesale shop's prices; IQR + 3× median flags 0.6%.
4. **Reproducibility must be tested, not assumed.** Two hidden bugs (row order, decimal sums) only showed up when we ran the flow twice and compared.
5. **A missing value can't be cleaned away.** Guest orders stay; we only document what they can't be used for.
6. **Reference data needs cleaning too.** The country file had 50 comment lines and different spellings.

---

## 9. For the report: reflection (what we could not fix, who did what)

**What we could not fix:**
- 243,007 raw lines (22.8%) without a Customer ID: the information was never recorded.
- Which description is "right" for 599 products: we chose the most used one, an explainable rule but not a certainty.
- "Channel Islands", "European Community", "West Indies", "Unspecified" are not countries: 2,403 trusted lines have no ISO code.
- Our DOI: needs the Zenodo upload (TO CONFIRM).
- The data ends in December 2011; we can't make it current.

**Who did what:** TO CONFIRM. Suggested split for 4 members:

| Member | Part |
|---|---|
| A | dataset, problem statement, architecture, FAIR |
| B | profiling |
| C | Tableau Prep flow |
| D | Script steps (pipeline), governance, conclusion |

**Report appendix:**
- metadata record: `fair/original_metadata_record.json` + `fair/metadata.json`;
- cleaning log: the flow's Changes panes + `reports/verification.md`;
- data dictionary: `governance/data_dictionary.md`;
- link to the code (GitHub).

---

## 10. How to show the flow live in Tableau Prep

1. **Before the presentation**, start TabPy in a terminal: `.venv/bin/python tools/run_tabpy_local.py`.
2. Open `prep/online_retail_flow.tfl` in Tableau Prep Builder.
   - The TabPy connection is already set in this computer's Tableau Prep repository.
   - On another computer, set it once: Help › Settings and Performance › Manage Analytics Extension Connection › TabPy, `localhost`, `9004`.
3. Click a step to show its **profile pane** and **Changes pane**:
   - the Input steps 1a/1b (the Invoice type change to String);
   - step 3 (15 changes);
   - step 4 (rows 1,067,371 → 1,033,036);
   - step 6 (the Script step and its file/function);
   - step 8 (the join's Venn diagram and the unmatched countries);
   - steps 10a-d (the split).
4. **Run Flow** (▶) takes about 1.5 minutes. Show the row counts.
5. For screenshots of the full flow: View › Zoom to fit.

**The packaged flow** `prep/online_retail_flow.tflx` (45 MB) contains the raw data. It is the file for the submission ZIP.

On **another computer**, two paths must match that computer:
- the output folders (`data/output`, `data/warehouse`);
- the two Script files (`prep/script_*.py`).

Either run `.venv/bin/python tools/build_flow.py --packaged` there once, which writes the paths for that computer, or change the paths in the Output and Script steps by hand. That's why the project folder or the GitHub link goes into the ZIP as well.

**If the app shows a step in red:**
1. Is TabPy running? (Script steps need it.)
2. Is the analytics-extension connection set to `localhost:9004`?
3. Do the output folders exist?

---

## 11. Problems we met while building it (good answers to "what was difficult?")

| Problem | What we saw | Cause | Fix |
|---|---|---|---|
| The command-line runner rejected the flow file | `NullPointerException` while reading it | our file stored each step's type (`nodeType`) not first in the JSON; Prep's reader needs the type first | write `nodeType` first |
| The flow crashed in the Tableau Prep **app** (a "panic" dialog), although the command-line run worked | crash right after opening | the app's editor treats any text starting with `{` and ending with `}` as an old **parameter name**; our two LOD formulas `{FIXED ...}` look exactly like that. Prep itself saves them as `{{FIXED ...}}` | write LOD formulas with doubled braces (found in the app's own code, function `unescapeOldParameterSyntax`) |
| Red errors in the app ("unknown field", "conflicting types") | only in the app, never in the command-line run | (1) the app **re-detects the Excel column types**: `Invoice` → number, so `STARTSWITH([invoice], "C")` failed; (2) the automatic field "Source Row Number" exists in the command-line run but **not** in the app, so renaming it failed | change Invoice to String **in the Input step** (as a user would); stop using Source Row Number |
| Outputs not found when opening the `.tflx` | "parent folder doesn't exist: /data/output" | the app unpacks a `.tflx` into a temporary folder, so paths relative to the flow file point nowhere | full output paths |
| How we verified the fix | the app's own logs: no crash, no exception, and `flowExecutionErrorInfo={}` (the app previewed the whole flow, incl. both Script steps, without an error) | a flow that is already open is only brought to the front, not reloaded | we always opened a **fresh copy** to force a real load |
| TabPy refused the data | "413 Request too large" | Prep sends all ~1 million lines (232 MB) at once; TabPy's limit is 100 MB | `tools/tabpy.conf`: 1 GB limit, 15 min time limit |
| Every row failed rule R5 | 1,033,036 lines quarantined | Prep sends dates as `2010-09-14T16:25:00Z[UTC]` | `to_datetime()` removes `[UTC]` |
| Script step 2 crashed | `NaT has no attribute normalize` | Prep first calls the Script step with **0 rows** to check it | handle the empty table |
| Results changed between runs | different segment counts and revenue decimals | row order + decimal arithmetic | sort before ranking; round money to pence |
| Plain IQR flagged 15% of prices | 149,370 flags | quantity-discount price tiers, IQR = 0 for most products | IQR **and** ≥3× median |
| Dates in the CSV depended on the computer | `18/04/2011` | Prep writes dates in the computer's language format | export dates as ISO text |

---

## 12. Exam requirement checklist
| Requirement | Where it is met |
|---|---|
| ≥ 1,000 rows, two related tables, a date column, real quality problems, open licence | §1, `reports/profiling.md` |
| problem statement: which problem, for whom | §1.3, `README.md` |
| architecture: ETL/ELT, where Tableau Prep and Python run, storage (lake, warehouse) | §2 |
| FAIR score of the original + metadata record | §3, `fair/` |
| profiling: quality KPIs, column profile, the most important issues | §4, `reports/profiling.md`, figures |
| Tableau Prep: full flow, clean, union/join, calculated fields, aggregate, output, rows before → after | §5, `prep/online_retail_flow.tfl` |
| cleaning steps as functions: run on their own or in Prep's Script step, re-run on new data with the same result | §6, `prep/script_*.py`, `tests/`, `reports/reproducibility_check.md` |
| governance: roles, lineage, data dictionary, AI risks | §7, `governance/` |
| conclusion + lessons learned | §8 |
| report: ~8 pages + reflection; appendix (metadata, cleaning log, dictionary, code link) | §9 |
| ZIP `DM_Project_Group<Nr>.zip`: slides, report PDF, `.tflx`, notebook/code, GitHub link | `.tflx` ✔, code ✔; slides and report still to make |

---

## 13. Questions the professor may ask, with short answers
- **Why ETL, not ELT?** Decisions about what is a sale must be made before anyone uses the data; Prep is an ETL tool; the data is small. We still keep the raw copy, so we can always re-run.
- **Where is your "union" and where is your "join"?** Union: the two yearly sheets (step 2). Join: sales + GeoNames countries (step 8, left join).
- **Why a left join?** An inner join would silently delete 2,403 trusted lines whose "country" is not a real country.
- **Why remove duplicates after cleaning the text?** "LUNCH BAG  BLACK" and "lunch bag black" are only identical after standardising.
- **How do you know no line was lost?** The sum of `copies` over the four line outputs = 1,067,371 = the raw rows.
- **Why not delete cancellations?** They are real business events; deleting them would hide 1.46 M GBP of returns.
- **Why keep lines without a customer?** They are real sales (revenue); they are only excluded from RFM, where a customer is needed.
- **Why is plain IQR not enough here?** Most products have one dominant price, so IQR = 0 and every discount tier would be flagged. We require a 3× jump as well.
- **What does the Script step do that Prep can't?** It runs version-controlled, unit-tested Python functions: the same rules on every run and in the tests.
- **How did you prove reproducibility?** Two runs → identical fingerprints for all 7 outputs; first-year-only vs both years → identical decisions for all 518,596 first-year lines.
- **What does RFM mean and why is it AI-ready?** Recency, Frequency, Monetary: numeric, scaled 1-5, one row per customer, documented, no free text. Direct input for a classifier or clustering.
- **Is the customer ID personal data?** It is pseudonymous, but with country and purchases a small business or person could be identified, so we classify it as confidential.
- **Why is the original FAIR score 6 and not 8?** I and R are weak: Excel format, non-standard names, and documentation that doesn't match the file.
- **What would you do with more time?** Publish on Zenodo (DOI); train the "buys again" model with a time-based split; add GitHub CI that runs the tests and the flow on every change.

## 14. Glossary
- **CC BY 4.0:** a licence allowing reuse with credit.
- **Copies:** our counter of how many identical raw lines became one row.
- **Data contract:** an agreement between producer and users about schema, quality and changes.
- **Fingerprint:** a SHA-256 of an output's sorted rows; equal fingerprints = equal content.
- **FD:** functional dependency (A always gives the same B).
- **Hyper:** Tableau's analytical database file.
- **IQR:** interquartile range, Q3 − Q1.
- **LOD:** a level-of-detail expression in Tableau, `{FIXED [x] : AGG([y])}`.
- **Quarantine:** rows held back with a reason.
- **RFM:** Recency, Frequency, Monetary.
- **Schema drift:** columns renamed, added or removed between files.
- **Script step:** a Tableau Prep step that sends rows to Python (TabPy) and gets rows back.
- **TabPy:** Tableau's Python server.
- **Union / Join:** stack rows / add columns by a key.
