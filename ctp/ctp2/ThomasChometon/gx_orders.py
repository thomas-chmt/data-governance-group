"""CTP 2 - Exercise 3: expectation suite for ShopFast orders (GX Core 1.x) - 12 expectations.
Run:  python gx_orders.py   (works from any folder)
- builds the Data Docs in CTP 2/gx/uncommitted/data_docs/local_site/index.html
- adds every FAILING expectation to quality_scorecard.csv (rows starting with "orders:")
"""
from pathlib import Path
import pandas as pd
import great_expectations as gx

HERE = Path(__file__).parent
KIT = HERE.parent / "shopfast-kit" / "data"
orders = pd.read_csv(KIT / "orders.csv", dtype=str)
customers = pd.read_csv(KIT / "customers.csv", dtype=str)
orders["total_amount_eur"] = pd.to_numeric(orders["total_amount_eur"], errors="coerce")
orders["order_date_dt"] = pd.to_datetime(orders["order_date"], format="%Y-%m-%d", errors="coerce")  # typed copy for range checks

context = gx.get_context(mode="file", project_root_dir=HERE)   # creates CTP 2/gx/ (config + Data Docs)
source = context.data_sources.add_or_update_pandas("shopfast")
asset = source.add_dataframe_asset(name="orders")
batch_def = asset.add_batch_definition_whole_dataframe("all_orders")

suite = context.suites.add_or_update(gx.ExpectationSuite(name="orders_suite"))
E = gx.expectations

# Each rule = (expectation, dimension, plain words, severity, who fixes it, why this rule)
# Severity follows the quality policy of slide 14 (critical / high / medium / low).
RULES = [
    (E.ExpectTableRowCountToBeBetween(min_value=1000, max_value=100000),
     "Completeness", "the daily file is not empty or truncated", "critical", "Custodian",
     "a file with < 1000 orders means the export broke"),
    (E.ExpectColumnValuesToNotBeNull(column="order_id"),
     "Completeness", "order_id is filled", "critical", "Custodian", "an order without id cannot be invoiced"),
    (E.ExpectColumnValuesToBeUnique(column="order_id"),
     "Uniqueness", "order_id is unique", "critical", "Custodian", "a duplicate order is invoiced twice (slide 14)"),
    # TODO 1: customer_id must not be null
    (E.ExpectColumnValuesToNotBeNull(column="customer_id"),
     "Completeness", "customer_id is filled", "high", "Steward", "an order must belong to a customer"),
    # TODO 2: customer_id must exist in customers (foreign-key check)
    (E.ExpectColumnValuesToBeInSet(column="customer_id", value_set=sorted(set(customers["customer_id"].dropna()))),
     "Consistency", "customer_id exists in customers", "high", "Steward",
     "orphan orders cannot be shipped or invoiced: quarantine them (slide 14)"),
    # TODO 3: order_date must not be null and must look like YYYY-MM-DD
    (E.ExpectColumnValuesToNotBeNull(column="order_date"),
     "Completeness", "order_date is filled", "medium", "Custodian", "needed for revenue per day and timeliness"),
    (E.ExpectColumnValuesToMatchRegex(column="order_date", regex=r"^\d{4}-\d{2}-\d{2}$"),
     "Validity", "order_date is YYYY-MM-DD", "medium", "Custodian", "one date format so every tool reads it the same way"),
    # TODO 4: no order in the future
    (E.ExpectColumnValuesToBeBetween(column="order_date_dt", max_value=pd.Timestamp.now().normalize() + pd.Timedelta(days=1)),
     "Accuracy", "order_date is not in the future", "high", "Owner", "an order cannot be placed tomorrow: wrong clock or typo"),
    # TODO 5: status only in the 5 business values (looked at the data: SHIPPED, Delivered, 'delivered ', canceled exist)
    (E.ExpectColumnValuesToBeInSet(column="status", value_set=["pending", "shipped", "delivered", "cancelled", "returned"]),
     "Validity", "status is one of the 5 allowed values", "medium", "Steward",
     "badly spelled status is lost in reports: fix in transform and log it (slide 14)"),
    # TODO 6: channel and shipping_country only in their allowed values (value_counts() shows exactly these)
    (E.ExpectColumnValuesToBeInSet(column="channel", value_set=["web", "mobile_app", "marketplace"]),
     "Validity", "channel is web / mobile_app / marketplace", "medium", "Steward", "the 3 sales channels ShopFast has"),
    (E.ExpectColumnValuesToBeInSet(column="shipping_country", value_set=["FR", "BE", "DE", "ES"]),
     "Validity", "shipping_country is FR / BE / DE / ES", "high", "Owner", "ShopFast only ships to these 4 countries"),
    # TODO 7: total_amount_eur strictly positive and below a sensible maximum
    (E.ExpectColumnValuesToBeBetween(column="total_amount_eur", min_value=0, strict_min=True, max_value=5000),
     "Accuracy", "total_amount_eur is > 0 and <= 5000", "critical", "Owner",
     "history max is 1400 EUR; <= 0 or > 5000 means a bug or the x100 cents error"),
]
for exp, *_ in RULES:
    suite.add_expectation(exp)
suite.save()

vd = context.validation_definitions.add_or_update(gx.ValidationDefinition(name="orders_validation", data=batch_def, suite=suite))
checkpoint = context.checkpoints.add_or_update(gx.Checkpoint(name="orders_checkpoint", validation_definitions=[vd],
                                                             actions=[gx.checkpoint.UpdateDataDocsAction(name="docs")]))
result = checkpoint.run(batch_parameters={"dataframe": orders})

print("\nSuite passed:", result.success, f"({len(RULES)} expectations)")
results = [r for vr in result.run_results.values() for r in vr.results]
for r in results:
    cfg = r.expectation_config
    print(f"{'PASS' if r.success else 'FAIL'}  {cfg.type:<45} {cfg.kwargs.get('column', ''):<18} unexpected={r.result.get('unexpected_count', '-')}")

# --- Step 7: write every failing expectation in the scorecard ---
rows = []
for r, (exp, dimension, words, severity, who, why) in zip(results, RULES):
    if r.success:
        continue
    failing = r.result.get("unexpected_count")
    if failing is None:          # table-level expectation (row count): the whole batch fails
        failing = len(orders)
    rows.append({
        "dimension": dimension,
        "rule_in_plain_words": f"orders: {words}",
        "column": r.expectation_config.kwargs.get("column", "(table)"),
        "how_you_measured_it": f"GX {r.expectation_config.type} - why: {why}",
        "failing_rows": int(failing),
        "total_rows": len(orders),
        "score_pct": round(100 * (1 - failing / len(orders)), 2),
        "severity_high_medium_low": severity,
        "who_should_fix_owner_steward_custodian": who,
    })

scorecard_path = HERE / "quality_scorecard.csv"
scorecard = pd.read_csv(scorecard_path, dtype=str) if scorecard_path.exists() else pd.DataFrame()
if not scorecard.empty:
    scorecard = scorecard[~scorecard["rule_in_plain_words"].str.startswith("orders:")]   # replace old orders rows
scorecard = pd.concat([scorecard, pd.DataFrame(rows, dtype=str)], ignore_index=True)
scorecard.to_csv(scorecard_path, index=False)
print(f"\n{len(rows)} failing expectations added to {scorecard_path.name}")
print("Open the report:", HERE / "gx" / "uncommitted" / "data_docs" / "local_site" / "index.html")
