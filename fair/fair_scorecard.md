# FAIR scorecard (Lab 1.2 method)

Each principle gets **0 = missing, 1 = partly, 2 = fully**, so the total is out of 8. The scores are honest: a 2 needs real evidence.

## Original dataset: UCI Online Retail II

| Principle | What we checked | Score | Evidence | Biggest gap |
|---|---|---|---|---|
| **F - Findable** | persistent ID, title, description, keywords, catalogue | **2 / 2** | DOI 10.24432/C5CG6D, listed in the UCI catalogue, title and description | no keywords (only "Business") |
| **A - Accessible** | standard protocol, open download, metadata stays | **2 / 2** | HTTPS download without login, DOI landing page stays | - |
| **I - Interoperable** | open format, standard vocabularies, units, clear names | **1 / 2** | readable column names, but... | Excel (.xlsx) instead of CSV; currency only in the web text; country names not standard (EIRE, RSA, USA, "Unspecified"); no codes (ISO) |
| **R - Reusable** | licence, provenance, documentation, quality info | **1 / 2** | CC BY 4.0, short variable list, citation | **documentation does not match the file** (InvoiceNo vs Invoice, UnitPrice vs Price, "5-digit StockCode" vs POST/85123A); undocumented overlap of the two sheets; no quality information, no provenance of the export |
| **Total** | | **6 / 8** | | |

## Our cleaned dataset, version 1.0.0

| Principle | Score | What we did |
|---|---|---|
| **F** | **1 / 2** (2 / 2 after a Zenodo DOI) | `fair/metadata.json` (schema.org Dataset, JSON-LD): name, description, 10 keywords, coverage, distributions. No DOI yet: only publication gives one, so claiming 2 would be dishonest |
| **A** | **1 / 2** (2 / 2 after Zenodo) | GitHub repository + re-download script with checksums; Zenodo = permanent HTTPS + DOI + metadata that stays even if data is withdrawn |
| **I** | **2 / 2** | CSV in UTF-8; ISO 8601 dates; unit in every money column name (`_gbp`); ISO 3166 country codes (`iso2`, `iso3`) and continent from GeoNames; schema.org vocabulary; Tableau Hyper for the warehouse |
| **R** | **2 / 2** | CC BY 4.0 kept with credit (`creditText`); provenance in every row (`source_sheet`, `copies`); the whole cleaning recipe is the flow file; every rule documented (`dq_reason`); data dictionary; KPIs before/after; version 1.0.0 |
| **Total** | **6 / 8 now -> 8 / 8 after Zenodo** | |

## Why both totals are 6 but mean different things
- The original is strong in **F and A**, because UCI gives it a DOI, and weak in **I and R**, because its format, names and documentation don't match.
- Ours is strong in **I and R**, because that is what cleaning and documentation fix. F and A wait only for the publication step, which needs the group's Zenodo account (marked TO CONFIRM).

## Licence check
CC BY 4.0 allows sharing and changing, also commercially, **if** we (1) credit the source, (2) link the licence and (3) say what we changed. `metadata.json` does all three. GeoNames is also CC BY 4.0, so combining both is allowed.
