# Online Retail II: a trusted, AI-ready sales dataset

Data Management group exam project, Prof. Dr. Mehrdad Jalali, SRH University Heidelberg.
Group members: 
    - Saarthak Joshi 
    - Vivek Attri 
    - Yash Kirankumar 
    - Bhaskaran Brindavan 
    - Nandeesh Venkatapura Siddaraju


> **Exam question:** *Can this data be trusted, reused and fed into an AI model, and how do you prove it?*

---

## 1. The project in 30 seconds

| | |
|---|---|
| **Data** | real sales of a UK online gift shop, Dec 2009 to Dec 2011: **1,067,371 order lines** ([UCI Online Retail II](https://doi.org/10.24432/C5CG6D), CC BY 4.0) + a country reference table ([GeoNames](https://www.geonames.org), CC BY 4.0) |
| **Two related tables** | sheet *Year 2009-2010* (525,461 rows) and sheet *Year 2010-2011* (541,910 rows): same columns, same customers and products |
| **Problem** | the shop's managers want reliable **revenue per month and country** and want to know **which customers will buy again**. Can the raw export be trusted for that? |
| **Cleaning** | done **only in Tableau Prep**: `prep/online_retail_flow.tfl` (34 steps) |
| **Reproducible pipeline** | Python functions running **inside Tableau Prep's Script steps** (`prep/script_*.py`) |
| **Answer** | **yes, with documented limits.** All 1,067,371 lines are accounted for (trusted, quarantined with a reason, cancellation, non-product or removed duplicate); the trusted table is 99.99% complete, 100% valid and 0% duplicated; two runs and a "new data" run give identical results |

**Want the details?** Read [`PROJECT_EXPLAINED.md`](PROJECT_EXPLAINED.md). It explains every step: what, why, how, theory and result.

---

## 2. What is in this folder

```
DM_Project_Final/
├── README.md                     ← you are here
├── PROJECT_EXPLAINED.md          ← the whole project explained, in the order of the exam slides
├── prep/                         ← TABLEAU PREP
│   ├── online_retail_flow.tflx       the flow + its data in one file (for the submission ZIP)
│   ├── online_retail_flow.tfl        the same flow, reading data/raw/
│   ├── online_retail_flow_first_year_only.tfl   the same flow on 2009-2010 only ("new data" test)
│   ├── script_quality_rules.py       Script step 1: quality rules R1-R6 + price outlier flag
│   └── script_rfm_features.py        Script step 2: customer features for AI (RFM)
├── data/
│   ├── raw/                      original files, never changed + SHA-256 checksums
│   ├── output/                   results of the flow (CSV)
│   └── warehouse/                fact_sales.hyper (Tableau's database file)
├── reports/                      profiling, verification, reproducibility check, charts (figures/)
├── fair/                         FAIR scorecard + metadata records (schema.org)
├── governance/                   roles, lineage, data dictionary, data contract, AI risks
├── tests/                        tests of the Script-step functions
├── profiling/                    profiling script (reads only)
├── tools/                        helper scripts (see section 6)
├── logs/                         run log of the Script steps
└── requirements.txt              Python package versions
```

**The outputs** (in `data/output/`):

| File | Rows | What it is |
|---|---|---|
| `fact_sales.csv` (+ `data/warehouse/fact_sales.hyper`) | 1,003,214 | trusted sales lines |
| `quarantine_lines.csv` | 6,021 | lines that broke a rule, with the reason |
| `cancellations.csv` | 19,103 | cancelled lines (real events, kept separately) |
| `non_product_lines.csv` | 4,698 | postage, fees, manual entries |
| `monthly_revenue.csv` | 562 | revenue per month and country |
| `dim_product.csv` | 4,707 | one name per product |
| `customer_features.csv` | 5,852 | AI-ready customer table (RFM scores + segment) |

---

## 3. Just look at the flow (no setup)

1. Install and activate **Tableau Prep Builder**.
2. Open **`prep/online_retail_flow.tflx`**.
3. Click any step to see its profile pane and its Changes pane (the cleaning log).

That is enough to show and explain the flow. Section 4 is only needed to **run** it.

---

## 4. Run the flow

You need:
- **Tableau Prep Builder** (activated);
- **Python 3.12**. The easiest way is [uv](https://docs.astral.sh/uv/): `curl -LsSf https://astral.sh/uv/install.sh | sh`.

Python is only needed because the two Script steps run Python through **TabPy** (Tableau's Python server). All other steps run in Tableau Prep itself.

### Step 1: go into this folder
```bash
cd "/path/to/DM_Project_Final"
```

### Step 2: install Python packages (once per computer)
```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

### Step 3: write this computer's paths into the flow (once per computer / folder)
The flow file contains full paths to the output folders and to the two Script files. Rebuild it after copying the folder anywhere:
```bash
.venv/bin/python tools/build_flow.py
.venv/bin/python tools/build_flow.py --packaged
```
`build_flow.py` only writes the flow *file*; it does not touch any data.

### Step 4: start TabPy (every time, before running the flow)
```bash
.venv/bin/python tools/run_tabpy_local.py
```
Leave this window open. "Address already in use" means it is already running, which is fine. Stop it with Ctrl-C.
It only accepts connections from your own computer, because TabPy without a password would let anyone on the network run code.

### Step 5: connect Tableau Prep to TabPy (once per computer)
In Tableau Prep: **Help › Settings and Performance › Manage Analytics Extension Connection** →
**Tableau Python (TabPy) Server**, server `localhost`, port `9004`, no sign-in → **Sign In**.

### Step 6: run
Open `prep/online_retail_flow.tfl` (or `.tflx`) → click **Run Flow** (▶ top left).
It takes about **1.5 minutes**, and the results are written to `data/output/` and `data/warehouse/`.

On a Mac you can also run it from the terminal:
```bash
tools/run_flow.sh prep/online_retail_flow.tfl
```

**On Windows:** use `.venv\Scripts\python.exe` instead of `.venv/bin/python`, and the Run button in Tableau Prep instead of `run_flow.sh`.

---

## 5. Check the results (optional, reads only)
```bash
.venv/bin/python tools/verify_outputs.py           # do all raw lines add up? KPIs after cleaning
.venv/bin/python tools/check_reproducibility.py    # run twice + "new data" test (about 4 min, Mac)
.venv/bin/python -m pytest tests                   # test the Script-step functions on their own
.venv/bin/python profiling/profile_raw.py          # profile the raw data again
.venv/bin/python tools/results_figures.py          # redraw the result charts
```
The results are written to `reports/`.

---

## 6. Helper scripts in `tools/` (none of them changes data)

| Script | What it does |
|---|---|
| `download_data.py` | downloads the raw files again (if `data/raw/` is empty) and records checksums |
| `build_flow.py` | writes the flow file (`.tfl` / `.tflx`) with this computer's paths |
| `run_tabpy_local.py` + `tabpy.conf` | starts TabPy safely (localhost only, 1 GB limit for ~1 million rows) |
| `run_flow.sh` | runs a flow with Tableau's command-line runner and shows errors (Mac) |
| `verify_outputs.py` | reconciliation, KPIs after cleaning, fingerprints of every output |
| `check_reproducibility.py` | runs the flow twice and on first-year data only, then compares |
| `results_figures.py` | draws the result charts |

---

## 7. Troubleshooting

| You see | Do this |
|---|---|
| a Script step is red: *"Unable to connect to TabPy"* | start TabPy (step 4) and set the connection (step 5) |
| *"Address already in use"* when starting TabPy | nothing to do: TabPy is already running |
| an Output step is red: *"parent folder doesn't exist"* | run step 3 again in this folder |
| `.venv/bin/python: no such file or directory` | you are not inside `DM_Project_Final` (step 1), or step 2 was not done |
| a step looks old / unchanged after a fix | close the flow window in Tableau Prep and open the file again |

---

## 8. For the submission
ZIP name: `DM_Project_Group<Nr>.zip`. It should contain:
- the slides;
- the report (PDF);
- `prep/online_retail_flow.tflx`;
- the code (this folder);
- the GitHub link.

Still to do: slides, report, GitHub link, group names (TO CONFIRM).
`data/output/fact_sales.csv` is about 230 MB. Leave it out of the ZIP if it is too big, because running the flow recreates it.

---

## 9. Licences and credit
- Chen, D. (2012). *Online Retail II* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D (CC BY 4.0)
- GeoNames country information, https://www.geonames.org (CC BY 4.0)

Our changes are listed in `PROJECT_EXPLAINED.md`, in the flow's Changes panes and in `fair/metadata.json`.
