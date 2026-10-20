"""
Synthetic data for the Card Top-up Failure Investigation.

Northwind Pay (fictional) lets users top up their wallet with a bank card
through three payment gateways. On 25 Aug 2026 cards from one issuer
("Issuer 03") start failing on every gateway. Everything here is generated.

Run:  python scripts/generate_data.py      (writes CSVs into ./data)
"""
import numpy as np
import pandas as pd
from pathlib import Path

rng = np.random.default_rng(20260825)
OUT = Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(exist_ok=True)
START, END = pd.Timestamp("2026-07-01"), pd.Timestamp("2026-10-12 23:59:59")
BREAK = pd.Timestamp("2026-08-25 09:40")

ISSUERS = {  # share of cards, normal acceptance
    "Issuer 01": (0.22, 0.86), "Issuer 02": (0.18, 0.84), "Issuer 03": (0.13, 0.85), "Issuer 04": (0.12, 0.80),
    "Issuer 05": (0.11, 0.83), "Issuer 06": (0.10, 0.78), "Issuer 07": (0.08, 0.82), "Issuer 08": (0.06, 0.75)}
GATEWAYS = (["Gateway A", "Gateway B", "Gateway C"], [0.50, 0.32, 0.18])
NORMAL_FAIL = (["Not sufficient funds", "Customer didn't finish", "3DS code timed out", "3DS cancelled by customer",
                "Blocked by the bank", "Payment not captured", "Invalid merchant"],
               [0.30, 0.25, 0.15, 0.12, 0.10, 0.05, 0.03])
# after the break, Issuer 03 fails with a gateway-specific reason (same root cause, different wording)
BROKEN_REASON = {"Gateway A": (["Invalid merchant", "Payment not captured"], [0.75, 0.25]),
                 "Gateway B": (["Declined at 3DS start", "3DS result unknown"], [0.8, 0.2]),
                 "Gateway C": (["Blocked by the bank", "Invalid merchant"], [0.7, 0.3])}
CITIES = (["Beirut", "Mount Lebanon", "North", "South", "Bekaa"], [0.42, 0.27, 0.12, 0.12, 0.07])

# ---------------------------------------------------------------- accounts and their cards
N_ACC = 9000
acc_created = pd.Timestamp("2023-01-01") + pd.to_timedelta(rng.integers(0, (END - pd.Timestamp("2023-01-01")).days, N_ACC), "D")
accounts = pd.DataFrame({
    "account_id": [f"W{200000 + i}" for i in range(N_ACC)],
    "created_at": acc_created,
    "region": rng.choice(CITIES[0], N_ACC, p=CITIES[1]),
    "kyc_level": rng.choice(["Basic", "Verified", "Verified+"], N_ACC, p=[0.25, 0.6, 0.15]),
})
# each account has a main card, and 30% have a second card from another issuer
iss_names, iss_p = list(ISSUERS), np.array([v[0] for v in ISSUERS.values()])
main_card = rng.choice(iss_names, N_ACC, p=iss_p)
second = np.where(rng.random(N_ACC) < 0.30, [rng.choice([i for i in iss_names if i != m]) for m in main_card], None)
cur = rng.choice(["USD", "LBP"], N_ACC, p=[0.82, 0.18])
brand = rng.choice(["Visa", "Mastercard"], N_ACC, p=[0.62, 0.38])

rows = []
aid = 9_000_000
days = pd.date_range(START.normalize(), END.normalize(), freq="D")
for day in days:
    n_sessions = rng.poisson(240 * (1.3 if day.day <= 3 else 1.0))
    accs = rng.integers(0, N_ACC, n_sessions)
    for a in accs:
        if accounts.created_at[a] > day:
            continue
        t0 = day + pd.Timedelta(seconds=int(rng.integers(7 * 3600, 24 * 3600 + 2 * 3600)))
        issuer, card_cur, card_brand = main_card[a], cur[a], brand[a]
        amount = float(np.round(np.clip(rng.lognormal(np.log(90), 1.0), 5, 5000), 0))
        gw = rng.choice(GATEWAYS[0], p=GATEWAYS[1])
        attempt = 0
        while True:
            attempt += 1
            broken = issuer == "Issuer 03" and t0 >= BREAK
            if broken:
                ok, reason = False, rng.choice(BROKEN_REASON[gw][0], p=BROKEN_REASON[gw][1])
            else:
                ok = rng.random() < ISSUERS[issuer][1]
                reason = None if ok else rng.choice(NORMAL_FAIL[0], p=NORMAL_FAIL[1])
            aid += 1
            rows.append(dict(attempt_id=f"T{aid}", attempted_at=t0, account_id=accounts.account_id[a], issuer=issuer,
                             card_brand=card_brand, card_currency=card_cur, gateway=gw, amount_usd=amount,
                             status="ACCEPTED" if ok else "DECLINED", failure_reason=reason))
            if ok:
                break
            # what does the customer do after a decline?
            r = rng.random()
            give_up = 0.30 if not broken else 0.22 + 0.06 * attempt
            if r < give_up or attempt >= 11:
                break
            if second[a] is not None and r < give_up + (0.10 if broken else 0.08) and issuer == main_card[a]:
                issuer = second[a]                       # switch to the other card
            elif rng.random() < 0.35:
                gw = rng.choice(GATEWAYS[0], p=GATEWAYS[1])  # app retries through another gateway
            if broken and rng.random() < 0.25:
                amount = float(max(5, np.round(amount * rng.choice([0.5, 0.25]), 0)))  # tries a smaller amount
            t0 = t0 + pd.Timedelta(minutes=float(rng.exponential(25 if broken else 15)))

A = pd.DataFrame(rows)
A = A[A.attempted_at <= END]

# ---- messiness the cleaning SQL handles
A["card_currency"] = A.card_currency.where(rng.random(len(A)) > 0.03, None)                      # currency missing
dup = A.sample(120, random_state=8)                                                              # webhook delivered twice
A = pd.concat([A, dup]).sort_values("attempted_at").reset_index(drop=True)
A["attempted_at"] = A.attempted_at.dt.strftime("%Y-%m-%d %H:%M:%S")
accounts["created_at"] = accounts.created_at.dt.strftime("%Y-%m-%d")
A.to_csv(OUT / "topup_attempts.csv", index=False)
accounts.to_csv(OUT / "accounts.csv", index=False)
print({"topup_attempts": len(A), "accounts": len(accounts)})
