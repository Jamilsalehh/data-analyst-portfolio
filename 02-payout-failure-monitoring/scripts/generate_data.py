"""
Synthetic data for the Cross-border Payout Failure Monitoring project.

"Northwind Pay" (fictional) sends money from Lebanon to banks and mobile
wallets abroad through a payout network partner. Every bank, ID and amount
below is generated. Bank names are codes on purpose (e.g. "EG Bank 02") so
they can't be confused with real institutions.

Run:  python scripts/generate_data.py      (writes CSVs into ./data)
"""
import hashlib
import numpy as np
import pandas as pd
from pathlib import Path

rng = np.random.default_rng(20260402)
OUT = Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(exist_ok=True)
START, END = pd.Timestamp("2026-04-01"), pd.Timestamp("2026-09-30 23:59:59")

# ---------------------------------------------------------------- dimensions
COUNTRIES = [  # code, name, region, currency, share of payouts, usd per unit (Apr), monthly drift, avg usd sent
    ("PH", "Philippines", "Asia", "PHP", 0.20, 0.0175, -0.002, 210),
    ("ET", "Ethiopia", "Africa", "ETB", 0.16, 0.0073, -0.012, 180),
    ("LK", "Sri Lanka", "Asia", "LKR", 0.12, 0.00333, 0.001, 190),
    ("BD", "Bangladesh", "Asia", "BDT", 0.12, 0.0082, -0.001, 200),
    ("EG", "Egypt", "Africa", "EGP", 0.12, 0.0205, -0.004, 260),
    ("NP", "Nepal", "Asia", "NPR", 0.08, 0.0074, -0.001, 170),
    ("IN", "India", "Asia", "INR", 0.07, 0.0116, -0.001, 300),
    ("GH", "Ghana", "Africa", "GHS", 0.05, 0.065, -0.006, 220),
    ("KE", "Kenya", "Africa", "KES", 0.05, 0.0077, 0.000, 200),
    ("SD", "Sudan", "Africa", "SDG", 0.03, 0.00166, -0.015, 160),
]
C = pd.DataFrame(COUNTRIES, columns=["country_code", "country_name", "region", "currency", "share", "usd_rate", "drift", "avg_usd"])

banks = []
for cc, share in zip(C.country_code, C.share):
    n_bank = 4 if share >= 0.1 else 3
    for i in range(1, n_bank + 1):
        banks.append((f"{cc}B{i:02d}", f"{cc} Bank {i:02d}", cc, "Bank account"))
    for i in range(1, 3 if share >= 0.1 else 2):
        banks.append((f"{cc}W{i:02d}", f"{cc} Wallet {i:02d}", cc, "Mobile wallet"))
    banks.append((f"{cc}C01", f"{cc} Cash Pickup 01", cc, "Cash pickup"))
B = pd.DataFrame(banks, columns=["bank_id", "bank_name", "country_code", "payout_type"])


def raw_variants(name):
    """How the partner's export spells the same bank on different days."""
    up = name.upper()
    return [name, up, name.replace(" ", ""), up + " LTD", name + " (" + name.split()[0] + ")", name.lower()]


bank_map = [(v, r.bank_id) for r in B.itertuples() for v in dict.fromkeys(raw_variants(r.bank_name))]
BM = pd.DataFrame(bank_map, columns=["bank_name_raw", "bank_id"])

TAXONOMY = [  # code, normalized message, category, owner, severity, escalate, retry_recommended, raw message variants
    ("000", "Paid", "Success", "-", "-", "No", "No", ["SUCCESS", "Transaction successful", "Paid out"]),
    ("R01", "Invalid account number", "Receiver details", "Customer Support", "Medium", "No", "No",
     ["Invalid Account Number", "INVALID_ACCOUNT", "acct invalid - check account no", "Beneficiary account not valid"]),
    ("R02", "Account name mismatch", "Receiver details", "Customer Support", "Medium", "No", "No",
     ["Name mismatch", "BENEFICIARY_NAME_MISMATCH", "Account holder name does not match"]),
    ("R03", "Account closed or dormant", "Receiver details", "Customer Support", "Low", "No", "No",
     ["Account closed", "ACCOUNT_DORMANT", "Account inactive/closed"]),
    ("R04", "Wallet not registered", "Receiver details", "Customer Support", "Low", "No", "No",
     ["Wallet not found", "MSISDN_NOT_REGISTERED", "Receiver wallet not registered"]),
    ("B01", "Receiving bank unavailable", "Bank / partner outage", "Partner Operations", "High", "Yes", "Yes",
     ["Bank unavailable", "DESTINATION_UNAVAILABLE", "Host down"]),
    ("B02", "Timeout from receiving bank", "Bank / partner outage", "Partner Operations", "High", "Yes", "Yes",
     ["Timeout", "BANK_TIMEOUT", "No response from bank within SLA"]),
    ("C01", "Held by compliance screening", "Compliance", "Compliance", "Medium", "Yes", "No",
     ["Compliance hold", "SANCTIONS_SCREENING_HIT", "Pending compliance review - rejected"]),
    ("C02", "Sender limit exceeded", "Limits", "Customer Support", "Low", "No", "No",
     ["Sender limit exceeded", "SENDER_LIMIT", "Monthly sender limit reached"]),
    ("C03", "Receiver limit exceeded", "Limits", "Customer Support", "Low", "No", "No",
     ["Receiver limit exceeded", "RECEIVER_LIMIT"]),
    ("F01", "Insufficient prefunding balance", "Treasury", "Finance", "Critical", "Yes", "Yes",
     ["Insufficient balance", "PREFUNDING_INSUFFICIENT", "Partner float too low"]),
    ("T01", "Duplicate transaction", "Technical", "Tech Team", "Medium", "Yes", "No",
     ["Duplicate", "DUPLICATE_TXN_ID"]),
    ("T02", "Invalid request format", "Technical", "Tech Team", "High", "Yes", "No",
     ["Invalid request", "SCHEMA_VALIDATION_FAILED", "Missing mandatory field"]),
]
T = pd.DataFrame([t[:7] for t in TAXONOMY], columns=["response_code", "normalized_message", "failure_category", "owner",
                                                    "severity", "escalate", "retry_recommended"])
MSG = {t[0]: t[7] for t in TAXONOMY}

# ---------------------------------------------------------------- transactions
days = pd.date_range(START.normalize(), END.normalize(), freq="D")
C_ROW = {r.country_code: r for r in C.itertuples()}
B_BY = {k: g.reset_index(drop=True) for k, g in B.groupby(["country_code", "payout_type"])}
rows = []
txn_no = 7_100_000
hour_p = np.array([1, 1, 1, 1, 1, 2, 3, 5, 7, 8, 8, 8, 7, 7, 7, 7, 7, 7, 6, 5, 4, 3, 2, 1], float)
hour_p /= hour_p.sum()
sender_pool = 21000
receivers_by_country = {cc: int(4000 * s / 0.2) + 300 for cc, s in zip(C.country_code, C.share)}

for day in days:
    # payday effect: more transfers in the first days of the month and on Sundays (day off for many senders)
    n = rng.poisson(390 * (1 + 0.35 * (day.day <= 4)) * (1.25 if day.weekday() == 6 else 1.0) * (1 + 0.08 * (day.month - 4) / 5))
    cc = rng.choice(C.country_code, n, p=C.share)
    hours = rng.choice(24, n, p=hour_p)
    for i in range(n):
        c = C_ROW[cc[i]]
        ptype = rng.choice(["Bank account", "Mobile wallet", "Cash pickup"], p=[0.55, 0.33, 0.12])
        cand = B_BY[(c.country_code, ptype)]
        w = np.array([0.5, 0.25, 0.15, 0.10][:len(cand)]); w /= w.sum()   # one dominant bank per country
        bank = cand.iloc[rng.choice(len(cand), p=w)]
        ts = day + pd.Timedelta(hours=int(hours[i]), seconds=int(rng.integers(3600)))
        usd = float(np.clip(rng.lognormal(np.log(c.avg_usd), 0.55), 20, 3000))
        months = (day.year - 2026) * 12 + day.month - 4
        rate = c.usd_rate * (1 + c.drift) ** months
        # ---- outcome model
        p = {"000": 0.915}
        if ptype == "Bank account":
            p.update({"R01": 0.022, "R02": 0.012, "R03": 0.004, "B01": 0.004, "B02": 0.006})
            if c.country_code == "ET":  # ET account numbers have no checksum in the app -> many typos
                p.update({"R01": 0.075, "R02": 0.02})
        elif ptype == "Mobile wallet":
            p.update({"R04": 0.03, "B02": 0.005})
        else:
            p.update({"R02": 0.008})
        p.update({"C01": 0.007, "C02": 0.004, "C03": 0.002, "T01": 0.002, "T02": 0.001})
        # prefunding runs low in the last days of each month
        if day.day >= 27:
            p["F01"] = 0.03
        # incidents: EG Bank 01 down 14 Jul 08:00 -> 15 Jul 16:00; PH Wallet 01 failing 22 Aug from 14:00;
        # ET Bank 01 intermittent timeouts 8-10 Sep
        incident = False
        if bank.bank_id == "EGB01" and pd.Timestamp("2026-07-14 08:00") <= ts < pd.Timestamp("2026-07-15 16:00"):
            p = {"000": 0.20, "B02": 0.60, "B01": 0.20}; incident = True
        if bank.bank_id == "PHW01" and pd.Timestamp("2026-08-22 14:00") <= ts < pd.Timestamp("2026-08-23 00:00"):
            p = {"000": 0.30, "B02": 0.70}; incident = True
        if bank.bank_id == "ETB01" and pd.Timestamp("2026-09-08") <= ts < pd.Timestamp("2026-09-11"):
            p = dict(p); p["B02"] = 0.30; incident = True
        codes = list(p)
        pr = np.array([p[k] for k in codes]); pr[0] = max(1 - pr[1:].sum(), 0.05); pr /= pr.sum()
        code = rng.choice(codes, p=pr)
        exec_s = float(rng.lognormal(np.log({"Bank account": 150, "Mobile wallet": 35, "Cash pickup": 60}[ptype]), 0.6))
        if code == "B02":
            exec_s = 300 + rng.uniform(0, 30)
        if bank.bank_id == "BDB03":  # a consistently slow bank
            exec_s *= 3.2
        txn_no += 1
        sender = f"S{rng.integers(sender_pool):05d}"
        receiver = f"{c.country_code}R{rng.integers(receivers_by_country[c.country_code]):05d}"
        status = "SUCCESS" if code == "000" else "FAILED"
        rows.append(dict(partner_txn_id=f"NWP{txn_no}", received_time=ts, last_update_time=ts + pd.Timedelta(seconds=exec_s),
                         status=status, payout_type=ptype, source_country="LB", destination_country=c.country_code,
                         destination_currency=c.currency, destination_amount=round(usd / rate, 2),
                         bank_name_raw=rng.choice(raw_variants(bank.bank_name), p=[0.6, 0.15, 0.08, 0.07, 0.05, 0.05]),
                         response_code=code, response_message=rng.choice(MSG[code]),
                         sender_id=sender, receiver_id=receiver, retry_of=None, _usd=usd, _bank=bank.bank_id))
        # ---- retries: ops staff retry many failures within 1-6 hours, often blindly
        if code != "000" and rng.random() < (0.55 if code in ("B01", "B02", "F01") else 0.35):
            if code in ("B01", "B02"):
                r_code = "000" if rng.random() < 0.85 else "B02"
            elif code == "F01":
                r_code = "000" if rng.random() < 0.7 else "F01"
            elif code in ("R01", "R02", "R03", "R04"):
                r_code = code if rng.random() < 0.93 else "000"
            else:
                r_code = code if rng.random() < 0.8 else "000"
            ts2 = ts + pd.Timedelta(minutes=int(rng.integers(60, 360)))
            if incident and code in ("B01", "B02") and ts2 < pd.Timestamp("2026-07-15 16:00") and ts.month == 7:
                r_code = "B02" if rng.random() < 0.6 else "000"
            txn_no += 1
            exec2 = 300 + rng.uniform(0, 30) if r_code == "B02" else float(rng.lognormal(np.log(90), 0.6))
            rows.append(dict(partner_txn_id=f"NWP{txn_no}", received_time=ts2, last_update_time=ts2 + pd.Timedelta(seconds=exec2),
                             status="SUCCESS" if r_code == "000" else "FAILED", payout_type=ptype, source_country="LB",
                             destination_country=c.country_code, destination_currency=c.currency,
                             destination_amount=round(usd / rate, 2), bank_name_raw=rng.choice(raw_variants(bank.bank_name)),
                             response_code=r_code, response_message=rng.choice(MSG[r_code]),
                             sender_id=sender, receiver_id=receiver, retry_of=f"NWP{txn_no - 1}", _usd=usd, _bank=bank.bank_id))

P = pd.DataFrame(rows).sort_values("received_time").reset_index(drop=True)
P = P[P.received_time <= END]

# ---- messiness the Power Query steps must handle
P["status"] = P["status"].where(rng.random(len(P)) > 0.05, P["status"].str.title())          # SUCCESS / Success
P["received_time"] = P["received_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
P["last_update_time"] = pd.to_datetime(P["last_update_time"]).dt.strftime("%Y-%m-%d %H:%M:%S")
dupe = P.sample(85, random_state=11)                                                          # partner re-sent rows
P = pd.concat([P, dupe]).sort_values("received_time").reset_index(drop=True)
# privacy: ids are already synthetic, but hash them the way a real export should be shared
for col in ("sender_id", "receiver_id"):
    P[col] = P[col].map(lambda s: hashlib.sha1(("nwp-" + s).encode()).hexdigest()[:12])

fx = []
for c in C.itertuples():
    for k, m in enumerate(pd.period_range("2026-04", "2026-09", freq="M")):
        fx.append((str(m), c.currency, round(c.usd_rate * (1 + c.drift) ** k, 8)))
FX = pd.DataFrame(fx, columns=["month", "currency", "usd_per_unit"])

P.drop(columns=["_usd", "_bank"]).to_csv(OUT / "payouts.csv", index=False)
C[["country_code", "country_name", "region", "currency"]].to_csv(OUT / "countries.csv", index=False)
B.to_csv(OUT / "banks.csv", index=False)
BM.to_csv(OUT / "bank_name_mapping.csv", index=False)
T.to_csv(OUT / "error_taxonomy.csv", index=False)
FX.to_csv(OUT / "fx_rates.csv", index=False)
print({"payouts": len(P), "banks": len(B), "bank_name_mapping": len(BM), "fx_rates": len(FX)})
