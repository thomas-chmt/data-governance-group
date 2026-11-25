"""CTP 2 - Exercise 1: profile customers.csv with pandas.
Run:  python profile_customers_starter.py   (works from any folder)
Measures 10 rules over 5 dimensions and writes them to quality_scorecard.csv next to this script.
"""
from pathlib import Path
import pandas as pd

HERE = Path(__file__).parent
df = pd.read_csv(HERE.parent / "shopfast-kit" / "data" / "customers.csv", dtype=str)   # dtype=str: keep the raw text (e.g. 01300)
n = len(df)
print("Rows:", n)
print(df.head())

rules = []   # one dict per rule -> becomes the scorecard


def add_rule(dimension, rule, column, how, failing, severity, who, total=n):
    """Store one rule and print its result."""
    rules.append({
        "dimension": dimension,
        "rule_in_plain_words": rule,
        "column": column,
        "how_you_measured_it": how,
        "failing_rows": int(failing),
        "total_rows": int(total),
        "severity_high_medium_low": severity,
        "who_should_fix_owner_steward_custodian": who,
    })
    print(f"[{dimension}] {rule}: {failing} failing / {total}")


# --- Completeness: how many empty values per column? ---
print("\nEmpty values per column:\n", df.isna().sum(), "\n")
add_rule("Completeness", "email is filled", "email", "isna().sum()",
         df["email"].isna().sum(), "medium", "Steward")
add_rule("Completeness", "phone is filled", "phone", "isna().sum()",
         df["phone"].isna().sum(), "low", "Steward")

# --- Uniqueness: is customer_id unique? ---
add_rule("Uniqueness", "customer_id is unique", "customer_id", "duplicated(keep=False)",
         df["customer_id"].duplicated(keep=False).sum(), "high", "Custodian")

# TODO 1 (Uniqueness): normalise email (strip + lower case) and count people registered twice
email_norm = df["email"].str.strip().str.lower()   # new variable: the raw column stays intact for TODO 2
add_rule("Uniqueness", "one account per email", "email",
         "strip+lower then duplicated(keep=False) on non-empty",
         email_norm.dropna().duplicated(keep=False).sum(), "medium", "Steward")

# TODO 2 (Validity): count emails that do not match the regex (empty emails are already counted in Completeness)
EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$"
add_rule("Validity", "email looks like an email", "email",
         f"regex {EMAIL_REGEX} on non-empty raw values",
         (~df["email"].dropna().str.match(EMAIL_REGEX)).sum(), "medium", "Owner")

# TODO 3 (Consistency): distinct values of country - how many spellings for 4 countries?
print("\nDistinct values of country:\n", df["country"].value_counts(dropna=False))
print("Number of spellings:", df["country"].nunique(), "\n")
add_rule("Consistency", "country is an ISO-2 code", "country", "not isin({FR DE ES BE}) on non-empty",
         (~df["country"].dropna().isin(["FR", "DE", "ES", "BE"])).sum(), "medium", "Custodian")

# TODO 4 (Consistency): signup_date values that are NOT in the format YYYY-MM-DD
add_rule("Consistency", "signup_date is YYYY-MM-DD", "signup_date", r"regex ^\d{4}-\d{2}-\d{2}$",
         (~df["signup_date"].str.match(r"^\d{4}-\d{2}-\d{2}$")).sum(), "low", "Custodian")

# TODO 5 (Validity): loyalty_tier values outside bronze / silver / gold / platinum
add_rule("Validity", "loyalty_tier is bronze/silver/gold/platinum", "loyalty_tier", "not isin(allowed list)",
         (~df["loyalty_tier"].isin(["bronze", "silver", "gold", "platinum"])).sum(), "medium", "Custodian")

# TODO 6 (Accuracy): plausible birth date = between 1906 and today - 18 years (only ISO dates are converted)
birth = pd.to_datetime(df["birth_date"], format="%Y-%m-%d", errors="coerce")   # non-ISO dates become NaT
adult_limit = pd.Timestamp.now() - pd.DateOffset(years=18)
add_rule("Accuracy", "birth date is plausible", "birth_date", "ISO dates before 1906 or after today-18y",
         ((birth < pd.Timestamp("1906-01-01")) | (birth > adult_limit)).sum(), "medium", "Owner")

# TODO 7 (Validity): French postal codes that do not have 5 digits
is_french = df["country"].str.strip().str.lower().isin(["fr", "france", "fra"])   # all spellings of France
french = df[is_french]
add_rule("Validity", "French postal code has 5 digits", "postal_code", r"regex ^\d{5}$ on French rows only",
         (~french["postal_code"].str.match(r"^\d{5}$")).sum(), "medium", "Steward", total=len(french))

# Bonus: score_pct = 100 * (1 - failing_rows / total_rows) for each rule, then save the scorecard