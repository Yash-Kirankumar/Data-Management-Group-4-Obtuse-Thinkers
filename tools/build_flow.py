"""Write the Tableau Prep flow file prep/online_retail_flow.tfl.

    python tools/build_flow.py                  # the full flow (both years)
    python tools/build_flow.py --first-year-only  # same flow, only 2009-2010 (the "new data" test)
    python tools/build_flow.py --packaged         # .tflx with the raw data inside (for the ZIP)

This script does NOT touch the data. It only writes the flow file - the recipe - in
the same JSON format Tableau Prep Builder itself saves (Clean steps as SuperTransform,
inputs via data connections, a layout for every step). Every formula of the flow is
therefore readable and versioned in this file. Open the .tfl in Tableau Prep Builder to
see, edit and run the flow; all cleaning and transformation happens inside Tableau Prep.
"""
import argparse
import json
import uuid
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREP = ROOT / "prep"
NS = uuid.UUID("2b9e4c1a-7d3f-4e5a-9c8b-1f2e3d4c5b6a")
FEATURES = json.loads((Path(__file__).parent / "prep_document_features.json").read_text())

STEP_COLOURS = {"input": "#86AF6A", "clean": "#3D7FA6", "union": "#CD677F", "join": "#CD677F",
                "aggregate": "#EFC637", "script": "#8BC2CA", "output": "#8C564B"}


def type_first(obj):
    """Tableau Prep reads a step only if its type ("nodeType" / "connectionType") is the
    FIRST field of the JSON object - otherwise it fails with a NullPointerException."""
    if isinstance(obj, list):
        return [type_first(x) for x in obj]
    if not isinstance(obj, dict):
        return obj
    obj = {k: type_first(v) for k, v in obj.items()}
    for key in ("connectionType", "nodeType"):
        if key in obj:
            obj = {key: obj[key], **{k: v for k, v in obj.items() if k != key}}
    return obj


def nid(name):
    """Stable id per step name, so rebuilding gives the same file."""
    return str(uuid.uuid5(NS, name))


def rgba(hex_css):
    return [str(int(hex_css[i:i + 2], 16)) for i in (1, 3, 5)] + ["1"]


class Flow:
    def __init__(self):
        self.nodes, self.connections, self.data_connections = {}, {}, {}
        self.initial, self.layout = [], {}

    def _edges(self, nxt):
        """nxt: 'Step name' or [('Step name', namespace), ...]"""
        targets = [(nxt, "Default")] if isinstance(nxt, str) else nxt
        return [{"namespace": "Default", "nextNodeId": nid(n), "nextNamespace": ns} for n, ns in targets]

    def _place(self, name, kind, x, y):
        c = STEP_COLOURS[kind]
        self.layout[nid(name)] = {"color": {"hexCss": c, "rgba": rgba(c)},
                                  "position": {"x": x, "y": y}, "size": {"width": 1, "height": 1}}

    def _connection(self, path, attributes):
        name = Path(path).name
        cid, dcid = nid("connection " + name), nid("data connection " + name)
        self.connections[cid] = {"connectionType": ".v1.SqlConnection", "id": cid, "name": name,
                                 "isPackaged": False, "connectionAttributes": attributes}
        self.data_connections[dcid] = {"connectionType": ".QueryDataConnection", "id": dcid, "name": name,
                                       "isPackaged": False, "baseConnectionId": cid,
                                       "modifiedConnectionAttributes": {}}
        return dcid

    def _input_common(self, name, dcid, fields, nxt, pos):
        self.initial.append(nid(name))
        self._place(name, "input", *pos)
        return {"name": name, "id": nid(name), "baseType": "input", "nextNodes": self._edges(nxt),
                "serialize": False, "description": None, "connectionId": dcid, "connectionAttributes": {},
                "fields": [{"name": f, "type": t, "collation": "LEN_RUS" if t == "string" else None}
                           for f, t in fields],
                "actions": [], "debugModeRowLimit": None, "originalDataTypes": {}, "randomSampling": None,
                "updateTimestamp": None, "restrictedFields": {}, "userRenamedFields": {},
                "selectedFields": None, "filters": None}

    def excel_input(self, name, filename, sheet, fields, nxt, pos, as_text=()):
        """as_text: columns Tableau Prep detects as numbers but that must be read as text.
        Stored exactly like a type change made by hand in the Input step: the detected type
        stays in `fields`, plus a ChangeColumnType action and an originalDataTypes note."""
        dcid = self._connection(filename, {"class": "excel-direct", "filename": filename,
                                           "cleaning": "no", "interpretationMode": "0"})
        node = self._input_common(name, dcid, fields, nxt, pos)
        if as_text:
            detected = dict(fields)
            node["actions"] = [{"nodeType": ".v1.ChangeColumnType", "name": f"Change {c} to string",
                                "id": nid(f"{name} :: as text :: {c}"), "baseType": "transform",
                                "nextNodes": [], "serialize": False, "description": None,
                                "fields": {c: {"type": "string", "calc": None}}} for c in as_text]
            node["originalDataTypes"] = {c: detected[c] for c in as_text}
        node.update({"nodeType": ".v2022_4_1.LoadExcel",
                     "relation": {"displayName": f"[{sheet}$]", "type": "table", "table": f"[{sheet}$]"}})
        self.nodes[node["id"]] = node

    def text_input(self, name, filename, fields, nxt, pos, separator=",", headers=True):
        dcid = self._connection(filename, {"class": "textscan", "filename": filename})
        node = self._input_common(name, dcid, fields, nxt, pos)
        node.update({"nodeType": ".v1.LoadCsv", "separator": separator, "locale": "en_US",
                     "charSet": "UTF-8", "containsHeaders": headers, "textQualifier": "\""})
        self.nodes[node["id"]] = node

    def clean(self, name, actions, nxt, pos, description=None):
        """A Clean step: every action is one line in its Changes pane."""
        annotations = []
        for i, a in enumerate(actions):
            node = {"name": a["name"], "id": nid(f"{name} :: {i} :: {a['name']}"), "baseType": "transform",
                    "nextNodes": [], "serialize": False, "description": None}
            node.update({k: v for k, v in a.items() if k != "name"})
            annotations.append({"namespace": "Default", "annotationNode": node})
        self._place(name, "clean", *pos)
        self.nodes[nid(name)] = {
            "nodeType": ".v2018_2_3.SuperTransform", "name": name, "id": nid(name), "baseType": "superNode",
            "nextNodes": self._edges(nxt), "serialize": False, "description": description,
            "beforeActionAnnotations": annotations, "afterActionAnnotations": [], "actionNode": None}

    def _super(self, node_type, kind, name, action, nxt, pos, description=None):
        self._place(name, kind, *pos)
        self.nodes[nid(name)] = {
            "nodeType": node_type, "name": name, "id": nid(name), "baseType": "superNode",
            "nextNodes": self._edges(nxt), "serialize": False, "description": description,
            "beforeActionAnnotations": [], "afterActionAnnotations": [],
            "actionNode": dict(action, name=name, id=nid(name + " action"), baseType="transform",
                               nextNodes=[], serialize=False, description=None)}

    def union(self, name, namespaces, nxt, pos):
        self._super(".v2018_2_3.SuperUnion", "union", name, {
            "nodeType": ".v1.SimpleUnion",
            "namespaceFieldMappings": [{"namespaceName": n, "fieldMappings": {}} for n in namespaces]}, nxt, pos)

    def join(self, name, left, right, join_type, nxt, pos):
        self._super(".v2018_2_3.SuperJoin", "join", name, {
            "nodeType": ".v1.SimpleJoin", "joinType": join_type,
            "conditions": [{"leftExpression": f"[{left}]", "rightExpression": f"[{right}]", "comparator": "=="}]},
            nxt, pos)

    def aggregate(self, name, group_by, aggregates, nxt, pos, description=None):
        """aggregates: (column, function, new name)"""
        self._super(".v2018_2_3.SuperAggregate", "aggregate", name, {
            "nodeType": ".v1.Aggregate",
            "groupByFields": [{"columnName": c, "function": None, "newColumnName": None, "specialFieldType": None}
                              for c in group_by],
            "aggregateFields": [{"columnName": c, "function": f, "newColumnName": n, "specialFieldType": None}
                                for c, f, n in aggregates]}, nxt, pos, description)

    def script(self, name, script_file, function, nxt, pos, description=None):
        params = {"scriptFilePath": str(script_file), "scriptFunctionName": function}
        self._super(".v2019_2_2.SuperExtensibilityNode", "script", name, {
            "nodeType": ".v2019_2_2.ExtensibilityNode", "externalServiceType": "pythonsupport",
            "setupParameters": dict(params), "executionParameters": dict(params)}, nxt, pos, description)

    def csv_output(self, name, path, pos):
        self._place(name, "output", *pos)
        self.nodes[nid(name)] = {"nodeType": ".v1.WriteToCsv", "name": name, "id": nid(name),
                                 "baseType": "output", "nextNodes": [], "serialize": False,
                                 "description": None, "csvOutputFile": str(path)}

    def hyper_output(self, name, path, pos):
        self._place(name, "output", *pos)
        self.nodes[nid(name)] = {"nodeType": ".v1.WriteToHyper", "name": name, "id": nid(name),
                                 "baseType": "output", "nextNodes": [], "serialize": False,
                                 "description": None, "hyperOutputFile": str(path),
                                 "tdsOutput": str(path.with_suffix(".tds"))}

    def save(self, path, packaged=False):
        data_files = {}
        if packaged:  # a .tflx carries its input files: Data/<connection id>/<file>
            for cid, c in self.connections.items():
                src = Path(c["connectionAttributes"]["filename"])
                data_files[cid] = (src, f"Data/{cid}/{src.name}")
                c["connectionAttributes"]["filename"] = src.name
                c["isPackaged"] = True
            for d in self.data_connections.values():
                d["isPackaged"] = True
        flow = {"parameters": {"parameters": {}}, "initialNodes": self.initial, "nodes": self.nodes,
                "connections": self.connections, "dataConnections": self.data_connections,
                "connectionIds": list(self.connections), "dataConnectionIds": list(self.data_connections),
                "nodeProperties": {}, "extensibility": {}, "selection": [],
                "majorVersion": 1, "minorVersion": 9, "documentId": nid("document"), "obfuscatorId": None}
        display = {"majorVersion": 1, "minorVersion": 0,
                   "fieldOrder": {"fieldOrdinals": {}, "minOrdinal": 0, "maxOrdinal": 0},
                   "flowDisplaySettings": {"flowGroupNodeDisplay": {},
                                           "flowSelection": {"type": "", "selectedNodePath": "", "selectedType": ""},
                                           "flowNodeDisplaySettings": self.layout}}
        meta = {"majorVersion": 1, "minorVersion": 0, "flowEntryName": "flow",
                "displaySettingsEntryName": "displaySettings", "isPackagedMaestroDocument": packaged,
                "documentFeaturesUsedInDocument": FEATURES}
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("flow", json.dumps(type_first(flow), indent=1, ensure_ascii=False))
            z.writestr("displaySettings", json.dumps(display, indent=1))
            z.writestr("maestroMetadata", json.dumps(meta, indent=1, ensure_ascii=False))
            for src, arc in data_files.values():
                z.write(PREP / src, arc)   # src is relative to the flow folder


# ---------------------------------------------------------------- actions: one Changes-pane line each

def calc(col, expr, name=None):
    # Tableau Prep's editor reads text that starts with "{" and ends with "}" as an old-style
    # parameter name and crashes. Prep itself stores level-of-detail formulas such as
    # {FIXED [x] : MAX([y])} with doubled braces, so we do the same.
    if expr.startswith("{") and expr.endswith("}"):
        expr = "{" + expr + "}"
    return {"nodeType": ".v1.AddColumn", "columnName": col, "expression": expr, "name": name or f"Calculate {col}"}


def rename(col, new):
    return {"nodeType": ".v1.RenameColumn", "columnName": col, "rename": new, "name": f"Rename {col} to {new}"}


def remove(cols, name):
    return {"nodeType": ".v1.RemoveColumns", "columnNames": cols, "name": name}


def change_type(types, name):
    return {"nodeType": ".v1.ChangeColumnType", "name": name,
            "fields": {c: {"type": t, "calc": None} for c, t in types.items()}}


def iso_text(cols):
    """CSV export: dates as ISO 8601 text (2010-12-01), the same on every computer and language
    setting. Without this, Prep writes dates in the computer's local format (01/12/2010)."""
    return [calc(c, f"STR([{c}])", f"Export {c} as ISO text") for c in cols]


def round_money(col):
    """Sums of decimal prices are not exact in a computer (8768.27 can become 8768.270000000001)
    and the tiny error depends on the order of adding - which changes between runs.
    Money is rounded to pence, so every run gives exactly the same number."""
    return calc(col, f"ROUND([{col}], 2)", f"Round {col} to pence")


def keep_only(expr, name):
    return {"nodeType": ".v1.FilterOperation", "filterExpression": expr, "name": name}


# ---------------------------------------------------------------- the flow

RAW = "../data/raw"          # paths are relative to the flow file in prep/
# The types Tableau Prep itself detects in the Excel sheets. Invoice is detected as a number
# (most invoices are 6 digits) - read that way, "C489449" would become empty. So Invoice is
# changed to text in the Input step (INVOICE_AS_TEXT), exactly as a user would do it.
SALES_FIELDS = [("Invoice", "integer"), ("StockCode", "string"), ("Description", "string"),
                ("Quantity", "integer"), ("InvoiceDate", "datetime"), ("Price", "real"),
                ("Customer ID", "integer"), ("Country", "string")]
INVOICE_AS_TEXT = ("Invoice",)

SALES_DATES = ["invoice_datetime", "invoice_date", "invoice_month"]

# Retail country names -> the names used by the GeoNames reference table.
COUNTRY_CASE = """CASE [country_raw]
WHEN "EIRE" THEN "Ireland"
WHEN "Netherlands" THEN "The Netherlands"
WHEN "USA" THEN "United States"
WHEN "RSA" THEN "South Africa"
WHEN "Korea" THEN "South Korea"
WHEN "Czech Republic" THEN "Czechia"
WHEN "Unspecified" THEN NULL
ELSE [country_raw] END"""

CONTINENT_CASE = """CASE [continent_code]
WHEN "EU" THEN "Europe" WHEN "AS" THEN "Asia" WHEN "AF" THEN "Africa"
WHEN "NA" THEN "North America" WHEN "SA" THEN "South America"
WHEN "OC" THEN "Oceania" WHEN "AN" THEN "Antarctica" END"""


def build(first_year_only=False):
    f = Flow()
    # the "new data" test writes to its own folders, so the real outputs stay untouched
    suffix = "_first_year_only" if first_year_only else ""
    # Outputs need full paths: Tableau Prep unpacks a .tflx into a temporary folder, so a path
    # relative to the flow file would point nowhere there. (Rebuild on another computer to update.)
    out, warehouse = ROOT / "data" / f"output{suffix}", ROOT / "data" / f"warehouse{suffix}"
    union_ns = ["Union-Namespace-" + nid("union 2009-2010"), "Union-Namespace-" + nid("union 2010-2011")]

    # 1. EXTRACT: the two sales tables and the country reference table
    if first_year_only:
        f.excel_input("1a Input - sales 2009-2010", f"{RAW}/online_retail_II.xlsx", "Year 2009-2010",
                      SALES_FIELDS, "3 Clean - names, types, text", (0, 1), INVOICE_AS_TEXT)
    else:
        f.excel_input("1a Input - sales 2009-2010", f"{RAW}/online_retail_II.xlsx", "Year 2009-2010",
                      SALES_FIELDS, [("2 Union - both years", union_ns[0])], (0, 0), INVOICE_AS_TEXT)
        f.excel_input("1b Input - sales 2010-2011", f"{RAW}/online_retail_II.xlsx", "Year 2010-2011",
                      SALES_FIELDS, [("2 Union - both years", union_ns[1])], (0, 2), INVOICE_AS_TEXT)
        # 2. UNION: stack both years (same 8 columns); Prep adds "Table Names" = the sheet
        f.union("2 Union - both years", union_ns, "3 Clean - names, types, text", (1, 1))
    f.text_input("1c Input - countries (GeoNames)", f"{RAW}/countryInfo.txt",
                 [(f"F{i}", "string") for i in range(1, 20)], "7 Clean - countries (reference)", (6, 4),
                 separator="\t", headers=False)

    # 3. CLEAN: readable names, one text format, customer id as text, country names
    lineage = ([calc("source_sheet", '"Year 2009-2010"', "Lineage: sheet name")] if first_year_only
               else [rename("Table Names", "source_sheet")])
    f.clean("3 Clean - names, types, text", lineage + [
        rename("Invoice", "invoice"),
        rename("StockCode", "stock_code"),
        rename("Description", "description"),
        rename("Quantity", "quantity"),
        rename("InvoiceDate", "invoice_datetime"),
        rename("Price", "unit_price_gbp"),
        rename("Customer ID", "customer_id_raw"),
        rename("Country", "country_raw"),
        calc("invoice", "UPPER(TRIM([invoice]))", "Invoice: trim spaces, upper case"),
        calc("stock_code", "UPPER(TRIM([stock_code]))", "Stock code: trim spaces, upper case"),
        calc("description", "UPPER(TRIM(REGEXP_REPLACE([description], '\\\\s+', ' ')))",
             "Description: one space between words, trim, upper case"),
        calc("customer_id", "IF ISNULL([customer_id_raw]) THEN NULL ELSE STR([customer_id_raw]) END",
             "Customer ID: number 13085 -> text 13085 (an ID is a label, not a number)"),
        remove(["customer_id_raw"], "Remove customer_id_raw"),
        calc("country", COUNTRY_CASE, "Country: standard names (EIRE -> Ireland, ...), Unspecified -> null"),
    ], "4 Aggregate - remove duplicate rows", (2, 1))

    # 4. DUPLICATES: identical lines collapse into one; 'copies' remembers how many there were
    f.aggregate("4 Aggregate - remove duplicate rows",
                ["invoice", "stock_code", "description", "quantity", "invoice_datetime", "unit_price_gbp",
                 "customer_id", "country_raw", "country"],
                [("source_sheet", "MIN", "source_sheet"), ("invoice", "COUNT", "copies")],
                "5 Clean - calculated fields", (3, 1),
                "Group by all 9 business columns: exact duplicate lines become one row. "
                "Overlapping December 2010 rows keep the first sheet as lineage.")
    # (Not used: Prep's automatic "Source Row Number". The command-line runner creates it for
    #  Excel files but the Tableau Prep app does not, so a flow using it breaks in the app.)

    # 5. CALCULATED FIELDS
    f.clean("5 Clean - calculated fields", [
        calc("invoice_date", "DATE([invoice_datetime])", "Invoice date (without time)"),
        calc("invoice_month", "DATE(DATETRUNC('month', [invoice_datetime]))", "Invoice month"),
        calc("is_cancellation", 'STARTSWITH([invoice], "C")', "Cancellation = invoice starts with C"),
        calc("line_type", 'IF [is_cancellation] THEN "cancellation" '
                          'ELSEIF REGEXP_MATCH([stock_code], "^[0-9]{5}") THEN "product" '
                          'ELSE "non_product" END', "Line type: product / non_product / cancellation"),
        calc("line_revenue_gbp", "ROUND([quantity] * [unit_price_gbp], 2)", "Revenue = quantity x unit price (in pence)"),
        calc("has_customer", "NOT ISNULL([customer_id])", "Has a customer ID?"),
    ], "6 Script - quality rules (Python)", (4, 1))

    # 6. SCRIPT STEP 1: the data-quality rules as Python functions (reproducible pipeline)
    f.script("6 Script - quality rules (Python)", ROOT / "prep" / "script_quality_rules.py",
             "apply_quality_rules", [("8 Join - add country data", "Left")], (5, 1),
             "Rules R1-R6 + IQR price flag -> dq_status, dq_reason, price_outlier_iqr")

    # 7. REFERENCE TABLE: clean the GeoNames country list
    f.clean("7 Clean - countries (reference)", [
        keep_only('NOT STARTSWITH([F1], "#")', "Remove the comment lines (start with #)"),
        rename("F1", "iso2"), rename("F2", "iso3"), rename("F5", "country_name"),
        rename("F8", "population"), rename("F9", "continent_code"),
        remove([f"F{i}" for i in (3, 4, 6, 7, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19)],
               "Remove columns we do not need"),
        change_type({"population": "integer"}, "Population as whole number"),
        calc("continent", CONTINENT_CASE, "Continent name from code"),
    ], [("8 Join - add country data", "Right")], (7, 4))

    # 8. JOIN: add ISO code, continent and population to every sales line (left join)
    f.join("8 Join - add country data", "country", "country_name", "left", "9 Clean - final fields", (8, 1))
    f.clean("9 Clean - final fields", [
        remove(["country_name"], "Remove the duplicate join key"),
        calc("country_matched", "NOT ISNULL([iso3])", "Country found in the reference table?"),
    ], [(n, "Default") for n in ["10a Clean - trusted sales", "10b Clean - quarantine",
                                 "10c Clean - cancellations", "10d Clean - non-product lines"]], (9, 1))

    # 10. SPLIT by dq_status -> four outputs (nothing disappears silently)
    f.clean("10a Clean - trusted sales", [keep_only('[dq_status] = "trusted"', "Keep trusted sales lines")],
            [(n, "Default") for n in ["Export - ISO dates (fact_sales)", "Output - warehouse fact_sales.hyper",
                                      "11 Aggregate - monthly revenue", "12 Clean - sales with a customer",
                                      "15 Aggregate - product descriptions"]], (10, 0))
    f.clean("Export - ISO dates (fact_sales)", iso_text(SALES_DATES), "Output - fact_sales.csv", (11, -2))
    f.csv_output("Output - fact_sales.csv", out / "fact_sales.csv", (12, -2))
    f.hyper_output("Output - warehouse fact_sales.hyper", warehouse / "fact_sales.hyper", (11, -1))
    for key, label, file, y in [("b", "quarantine", "quarantine_lines.csv", 2),
                                ("c", "cancellation", "cancellations.csv", 3),
                                ("d", "non_product", "non_product_lines.csv", 4)]:
        name = {"b": "10b Clean - quarantine", "c": "10c Clean - cancellations",
                "d": "10d Clean - non-product lines"}[key]
        f.clean(name, [keep_only(f'[dq_status] = "{label}"', f"Keep {label} lines")] + iso_text(SALES_DATES),
                f"Output - {file}", (10, y))
        f.csv_output(f"Output - {file}", out / file, (11, y))

    # 11. Monthly revenue per country (reporting)
    f.aggregate("11 Aggregate - monthly revenue", ["invoice_month", "country", "continent"],
                [("line_revenue_gbp", "SUM", "revenue_gbp"), ("invoice", "COUNTD", "invoices"),
                 ("quantity", "SUM", "units"), ("customer_id", "COUNTD", "customers")],
                "Export - ISO dates (monthly)", (11, 0))
    f.clean("Export - ISO dates (monthly)", [round_money("revenue_gbp")] + iso_text(["invoice_month"]),
            "Output - monthly_revenue.csv", (12, 0))
    f.csv_output("Output - monthly_revenue.csv", out / "monthly_revenue.csv", (13, 0))

    # 12-14. One row per customer -> SCRIPT STEP 2: RFM features for the AI model
    f.clean("12 Clean - sales with a customer", [keep_only("[has_customer]", "Keep lines with a customer ID")],
            "13 Aggregate - one row per customer", (11, 1))
    f.aggregate("13 Aggregate - one row per customer", ["customer_id"],
                [("country", "MIN", "country"), ("invoice_datetime", "MIN", "first_purchase"),
                 ("invoice_datetime", "MAX", "last_purchase"), ("invoice", "COUNTD", "invoices"),
                 ("invoice", "COUNT", "order_lines"), ("stock_code", "COUNTD", "products"),
                 ("line_revenue_gbp", "SUM", "revenue_gbp")],
                "13b Clean - round money", (12, 1))
    f.clean("13b Clean - round money", [round_money("revenue_gbp")], "14 Script - RFM features (Python)", (12, 2))
    f.script("14 Script - RFM features (Python)", ROOT / "prep" / "script_rfm_features.py", "rfm_features",
             "Export - ISO dates (customers)", (13, 1), "Recency, Frequency, Monetary scores and segments")
    f.clean("Export - ISO dates (customers)", iso_text(["first_purchase", "last_purchase"]),
            "Output - customer_features.csv", (14, 1))
    f.csv_output("Output - customer_features.csv", out / "customer_features.csv", (15, 1))

    # 15-17. One description per product (fixes StockCode -> Description conflicts)
    f.aggregate("15 Aggregate - product descriptions", ["stock_code", "description"],
                [("invoice", "COUNT", "lines_with_description")], "16 Clean - most common description", (11, -3))
    f.clean("16 Clean - most common description", [
        calc("descriptions_per_product", "{FIXED [stock_code] : COUNTD([description])}",
             "How many different descriptions this product has"),
        calc("max_lines", "{FIXED [stock_code] : MAX([lines_with_description])}",
             "Lines of the most used description"),
        keep_only("[lines_with_description] = [max_lines]", "Keep the most used description"),
    ], "17 Aggregate - one row per product", (12, -3))
    f.aggregate("17 Aggregate - one row per product", ["stock_code"],
                [("description", "MIN", "description"), ("descriptions_per_product", "MAX", "descriptions_found"),
                 ("lines_with_description", "MAX", "lines_with_this_description")],
                "Output - dim_product.csv", (13, -3))
    f.csv_output("Output - dim_product.csv", out / "dim_product.csv", (14, -3))
    return f


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--first-year-only", action="store_true")
    parser.add_argument("--packaged", action="store_true")
    args = parser.parse_args()
    name = "online_retail_flow" + ("_first_year_only" if args.first_year_only else "")
    path = PREP / (name + (".tflx" if args.packaged else ".tfl"))
    build(args.first_year_only).save(path, packaged=args.packaged)
    print("written", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
