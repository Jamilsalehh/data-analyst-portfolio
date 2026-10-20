"""
Reproduces the Power Query cleaning + DAX measures in pandas, so the numbers
in the README and the expected values in BUILD_GUIDE.md come from the data.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

D = Path(__file__).resolve().parents[1] / "data"
p = pd.read_csv(D / "payouts.csv", dtype={"response_code": str}, parse_dates=["received_time", "last_update_time"])
bm = pd.read_csv(D / "bank_name_mapping.csv")
banks = pd.read_csv(D / "banks.csv")
tax = pd.read_csv(D / "error_taxonomy.csv", dtype={"response_code": str})
fx = pd.read_csv(D / "fx_rates.csv")
out = {}

# ---- Power Query steps
raw_rows = len(p)
p = p.drop_duplicates()                                   # Remove duplicates
out["duplicates_removed"] = raw_rows - len(p)
p["status"] = p.status.str.upper()                        # Format > UPPERCASE
p = p.merge(bm, on="bank_name_raw", how="left")           # Merge bank mapping
out["unmapped_bank_rows"] = int(p.bank_id.isna().sum())
p["month"] = p.received_time.dt.strftime("%Y-%m")
p = p.merge(fx, left_on=["month", "destination_currency"], right_on=["month", "currency"], how="left")
p["usd_amount"] = (p.destination_amount * p.usd_per_unit).round(2)
p = p.merge(tax, on="response_code", how="left")
p["is_retry"] = p.retry_of.notna()
p["exec_s"] = (p.last_update_time - p.received_time).dt.total_seconds()
p["date"] = p.received_time.dt.date
p["hour"] = p.received_time.dt.hour
p = p.merge(banks[["bank_id", "bank_name"]], on="bank_id", how="left")
out["rows_clean"] = len(p)

# ---- KPIs (attempt level)
fail = p[p.status == "FAILED"]
out["attempts"] = len(p)
out["requests"] = int((~p.is_retry).sum())
out["retries"] = int(p.is_retry.sum())
out["attempt_success_rate"] = round((p.status == "SUCCESS").mean() * 100, 2)
out["usd_volume"] = round(p.loc[p.status == "SUCCESS", "usd_amount"].sum(), 0)
out["failed_usd"] = round(fail.usd_amount.sum(), 0)
# request level: did the money arrive in the end (first try or a retry)?
first = p[~p.is_retry].set_index("partner_txn_id")
retry_ok = p[p.is_retry & (p.status == "SUCCESS")].retry_of
first["final_success"] = (first.status == "SUCCESS") | first.index.isin(retry_ok)
out["first_try_success_rate"] = round((first.status == "SUCCESS").mean() * 100, 2)
out["final_success_rate"] = round(first.final_success.mean() * 100, 2)

# ---- failure mix
cat = fail.failure_category.value_counts()
out["failures"] = len(fail)
out["failure_share_by_category"] = (cat / cat.sum() * 100).round(1).to_dict()
own = fail.owner.value_counts()
out["failure_share_by_owner"] = (own / own.sum() * 100).round(1).to_dict()

# ---- Ethiopia account-number problem (bank accounts, first attempts)
ba = p[(p.payout_type == "Bank account") & ~p.is_retry]
r01 = ba.groupby("destination_country").apply(lambda g: (g.response_code == "R01").mean() * 100).round(2)
out["invalid_account_rate_by_country"] = r01.sort_values(ascending=False).to_dict()
et = ba[ba.destination_country == "ET"]
out["et_bank_requests"] = len(et)
out["et_receiver_detail_failures"] = int(et.response_code.isin(["R01", "R02"]).sum())
others_rate = ba[ba.destination_country != "ET"].response_code.isin(["R01", "R02"]).mean()
out["et_r01r02_rate"] = round(et.response_code.isin(["R01", "R02"]).mean() * 100, 2)
out["others_r01r02_rate"] = round(others_rate * 100, 2)
out["et_avoidable_if_like_others"] = int(round(out["et_receiver_detail_failures"] - len(et) * others_rate))

# ---- retries
r = p[p.is_retry].merge(p[["partner_txn_id", "response_code"]].rename(columns={"partner_txn_id": "retry_of", "response_code": "orig_code"}), on="retry_of")
r = r.merge(tax[["response_code", "retry_recommended"]].rename(columns={"response_code": "orig_code", "retry_recommended": "orig_retryable"}), on="orig_code")
g = r.groupby("orig_retryable").agg(retries=("partner_txn_id", "size"), success=("status", lambda s: (s == "SUCCESS").mean() * 100))
out["retries_by_original_retryable"] = g.round(1).reset_index().to_dict("records")
out["share_of_retries_on_non_retryable"] = round((r.orig_retryable == "No").mean() * 100, 1)

# ---- prefunding failures by day of month
f01 = fail[fail.response_code == "F01"]
out["f01_failures"] = len(f01)
out["f01_share_day27plus"] = round((pd.to_datetime(f01.date).dt.day >= 27).mean() * 100, 1)
out["f01_usd"] = round(f01.usd_amount.sum(), 0)

# ---- incident detection: bank-days where outage-type failures (timeouts / bank unavailable) spike.
# Receiver-detail failures are excluded on purpose: they are customer typos, not a bank problem.
p["is_outage_fail"] = (p.status == "FAILED") & (p.failure_category == "Bank / partner outage")
d = p.groupby(["bank_id", "date"]).agg(n=("status", "size"), outage=("is_outage_fail", "sum")).reset_index()
d["outage_rate"] = d.outage / d.n
d["incident"] = (d.outage >= 4) & (d.outage_rate >= 0.2)
inc = d[d.incident].sort_values(["date"])
out["incident_days"] = inc[["bank_id", "date", "n", "outage"]].astype(str).to_dict("records")
key = p.set_index(["bank_id", "date"]).index.isin(inc.set_index(["bank_id", "date"]).index)
out["incident_failed_attempts"] = int((key & (p.status == "FAILED")).sum())
out["incident_failed_usd"] = round(p[key & (p.status == "FAILED")].usd_amount.sum(), 0)
out["normal_bank_day_outage_rate"] = round(d[~d.incident].outage.sum() / d[~d.incident].n.sum() * 100, 2)

# ---- execution time
out["median_exec_s_by_type"] = p[p.status == "SUCCESS"].groupby("payout_type").exec_s.median().round(0).to_dict()
eb = p[(p.status == "SUCCESS") & (p.payout_type == "Bank account")].groupby("bank_id").exec_s.median().sort_values(ascending=False)
out["slowest_banks_median_s"] = eb.head(3).round(0).to_dict()

# ---- month trend
m = p.groupby("month").agg(attempts=("status", "size"), success=("status", lambda s: (s == "SUCCESS").mean() * 100))
out["monthly"] = m.round(2).reset_index().to_dict("records")
print(json.dumps(out, indent=1, default=str))
json.dump(out, open(Path(__file__).resolve().parents[1] / "scripts/expected_numbers.json", "w"), indent=1, default=str)
