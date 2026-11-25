"""CTP 2 - Exercise 4: replay the 'cents' incident.
A naive suite (not null / unique / allowed values) PASSES on payments_batch_2.csv although every amount is 100x too big.
Only value-range and distribution expectations catch it.
Run:  python gx_payments.py   (works from any folder)
Expected: history passes both suites, batch 2 passes the naive suite but FAILS the smart one.

Missing governance guard at ShopFast: a data contract - the payment team (producer) changed the unit of `amount`
from euros to cents without telling anyone, because nothing written and owned said "amount is in EUR with 2 decimals",
and no test enforced it before the data was loaded.
"""
from pathlib import Path
import pandas as pd
import great_expectations as gx

HERE = Path(__file__).parent
KIT = HERE.parent / "shopfast-kit" / "data"
files = {"payments (history)": KIT / "payments.csv", "payments_batch_2 (new)": HERE / "payments_batch_2.csv"}

context = gx.get_context(mode="file", project_root_dir=HERE)
source = context.data_sources.add_or_update_pandas("shopfast_payments")
asset = source.add_dataframe_asset(name="payments")
batch_def = asset.add_batch_definition_whole_dataframe("whole")
E = gx.expectations

naive = [E.ExpectColumnValuesToNotBeNull(column="payment_id"), E.ExpectColumnValuesToBeUnique(column="payment_id"),
         E.ExpectColumnValuesToNotBeNull(column="amount"), E.ExpectColumnValuesToBeInSet(column="currency", value_set=["EUR"]),
         E.ExpectColumnValuesToBeInSet(column="method", value_set=["card", "paypal", "apple_pay", "bank_transfer"])]

# History (payments.csv): min 13.70, median 184.31, mean 235.92, max 1400.79, always 2 decimals.
# Batch 2:                 min 980,   median 18488,  mean 18923,  max 37996,   never a decimal point.
smart = naive + [
    # 1. each payment between 0.01 and 5000 EUR (history max 1400 -> large safety margin)
    E.ExpectColumnValuesToBeBetween(column="amount", min_value=0.01, max_value=5000),
    # 2. the average basket stays in a normal range (history mean ~236 EUR)
    E.ExpectColumnMeanToBeBetween(column="amount", min_value=50, max_value=600),
    # 3. the median basket stays in a normal range (history median ~184 EUR)
    E.ExpectColumnMedianToBeBetween(column="amount", min_value=50, max_value=500),
    # 4. euros are written with a decimal point and 1-2 decimals ("54.5", "217.38"); cents have none ("7879")
    E.ExpectColumnValuesToMatchRegex(column="amount_txt", regex=r"^\d+\.\d{1,2}$"),
]

def run(name, expectations, df):
    suite = context.suites.add_or_update(gx.ExpectationSuite(name=name))
    for e in expectations: suite.add_expectation(e.copy() if hasattr(e, "copy") else e)
    suite.save()
    return batch_def.get_batch(batch_parameters={"dataframe": df}).validate(suite)

for label, path in files.items():
    df = pd.read_csv(path, dtype=str); df["amount_txt"] = df["amount"]; df["amount"] = pd.to_numeric(df["amount"])
    for suite_name, exps in [("naive_payments", naive), ("smart_payments", smart)]:
        res = run(suite_name, exps, df)
        failed = [r.expectation_config.type for r in res.results if not r.success]
        print(f"{label:<24} {suite_name:<15} success={res.success}  failed={failed}")
