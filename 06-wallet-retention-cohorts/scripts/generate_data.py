"""
Synthetic data for the Digital Wallet Retention & Cohorts project (built from scratch).

Northwind Pay (fictional) acquires users through five channels. The growth team
ran a social-ads push and a cashback promo in early 2026 and wants to know which
users stay, what predicts it, and whether the paid channels pay back.
Everything below is generated.

Outputs: data/users.csv, data/transactions.csv, data/marketing_spend.csv
"""
import numpy as np
import pandas as pd
from pathlib import Path

rng = np.random.default_rng(20251001)
OUT = Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(exist_ok=True)
END = pd.Timestamp("2026-09-30 23:59:59")
COHORTS = pd.period_range("2025-10", "2026-08", freq="M")

CH = {  # monthly retention if active last month, P(activate in 14d), never-transact share, txn rate factor
    "Referral": (0.86, 0.45, 0.05, 1.10),
    "Agent onboarding": (0.84, 0.55, 0.06, 1.00),
    "Organic": (0.78, 0.35, 0.10, 1.00),
    "Social ads": (0.63, 0.18, 0.16, 0.85),
    "Cashback promo": (0.45, 0.10, 0.03, 0.70),
}
REGIONS = (["Beirut", "Mount Lebanon", "North", "South", "Bekaa"], [0.38, 0.30, 0.12, 0.12, 0.08])
AGES = (["18-24", "25-34", "35-44", "45-54", "55+"], [0.22, 0.38, 0.22, 0.12, 0.06])
TYPES = ["Top-up", "P2P send", "Bill payment", "Merchant payment", "Cash-out", "Remittance"]
AMT = {"Top-up": 80, "P2P send": 40, "Bill payment": 35, "Merchant payment": 18, "Cash-out": 60, "Remittance": 150}


def revenue(t, amt):
    return {"Top-up": 0.0, "P2P send": max(0.2, amt * 0.01), "Bill payment": 0.5, "Merchant payment": amt * 0.012,
            "Cash-out": amt * 0.015, "Remittance": amt * 0.03}[t]


def channel_mix(m):
    mix = {"Referral": 0.22, "Agent onboarding": 0.24, "Organic": 0.30, "Social ads": 0.14, "Cashback promo": 0.10}
    if str(m) in ("2026-01", "2026-02", "2026-03"):                       # paid push
        mix.update({"Social ads": 0.34, "Cashback promo": 0.22 if str(m) != "2026-03" else 0.04})
    elif str(m) not in ("2025-12",):
        mix["Cashback promo"] = 0.02
    s = sum(mix.values())
    return {k: v / s for k, v in mix.items()}


def signups(m):
    base = 700 + 25 * (m - COHORTS[0]).n
    return int(base * (1.6 if str(m) in ("2026-01", "2026-02", "2026-03") else 1.0))


users, txns = [], []
uid, tid = 100000, 1
for m in COHORTS:
    mix = channel_mix(m)
    n = signups(m)
    chans = rng.choice(list(mix), n, p=list(mix.values()))
    for ch in chans:
        uid += 1
        r_base, p_act, p_never, rate = CH[ch]
        signup = m.start_time + pd.Timedelta(seconds=int(rng.integers(0, int((m.end_time - m.start_time).total_seconds()))))
        kyc = rng.choice(["Basic", "Verified"], p=[0.45, 0.55] if ch != "Cashback promo" else [0.75, 0.25])
        users.append(dict(user_id=f"U{uid}", signup_ts=signup, acquisition_channel=ch,
                          region=rng.choice(REGIONS[0], p=REGIONS[1]), age_band=rng.choice(AGES[0], p=AGES[1]),
                          kyc_level=kyc, device=rng.choice(["Android", "iOS"], p=[0.71, 0.29])))
        if rng.random() < p_never:
            continue
        activated = rng.random() < p_act
        r = min(0.95, r_base + (0.08 if activated else -0.06))
        lam = (6.0 if activated else 3.2) * rate * (1.2 if kyc == "Verified" else 1.0)
        # month 0 activity: first top-up soon after signup; activated users do a bill/merchant payment within 14 days
        t0 = signup + pd.Timedelta(hours=float(rng.exponential(30)))
        events = [(t0, "Top-up")]
        if activated:
            events.append((t0 + pd.Timedelta(days=float(rng.uniform(0.2, 13.5))), rng.choice(["Bill payment", "Merchant payment"])))
        else:
            # make sure non-activated users really have no bill/merchant payment in their first 14 days
            pass
        active_prev = True
        month_idx = 0
        while True:
            month_start = (m + month_idx).start_time
            month_end = (m + month_idx).end_time
            if month_start > END:
                break
            if month_idx == 0:
                active = True
            else:
                active = rng.random() < (r if active_prev else 0.10)
            if active:
                k = max(1, rng.poisson(lam))
                lo = max(month_start, signup)
                span = (min(month_end, END) - lo).total_seconds()
                if span > 0:
                    if activated:
                        p = [0.28, 0.22, 0.20, 0.18, 0.10, 0.02]
                    else:
                        p = [0.40, 0.33, 0.0, 0.0, 0.24, 0.03]
                    for _ in range(k):
                        ts = lo + pd.Timedelta(seconds=float(rng.uniform(0, span)))
                        t = rng.choice(TYPES, p=p)
                        if not activated and t in ("Bill payment", "Merchant payment"):
                            t = "P2P send"
                        # non-activated users may discover bill pay later, but never in the first 14 days
                        if not activated and month_idx >= 2 and rng.random() < 0.08:
                            t = "Bill payment"
                        events.append((ts, t))
            active_prev = active
            month_idx += 1
        for ts, t in events:
            if ts > END:
                continue
            amt = float(np.round(np.clip(rng.lognormal(np.log(AMT[t]), 0.7), 1, 3000), 2))
            ok = rng.random() > 0.03
            tid += 1
            txns.append(dict(txn_id=f"T{tid:08d}", user_id=f"U{uid}", txn_ts=ts, txn_type=t, amount_usd=amt,
                             revenue_usd=round(revenue(t, amt), 2) if ok else 0.0,
                             status="completed" if ok else "failed"))

U = pd.DataFrame(users)
T = pd.DataFrame(txns).sort_values("txn_ts").reset_index(drop=True)
U["signup_ts"] = U.signup_ts.dt.strftime("%Y-%m-%d %H:%M:%S")
T["txn_ts"] = pd.to_datetime(T.txn_ts).dt.strftime("%Y-%m-%d %H:%M:%S")

# marketing spend by month and channel (what each channel cost to acquire its users)
COST = {"Referral": 3.0, "Agent onboarding": 2.0, "Organic": 0.0, "Social ads": 11.0, "Cashback promo": 5.0}
sp = U.assign(month=pd.to_datetime(U.signup_ts).dt.to_period("M").astype(str)).groupby(["month", "acquisition_channel"]).size().reset_index(name="signups")
sp["spend_usd"] = (sp.signups * sp.acquisition_channel.map(COST) * rng.uniform(0.9, 1.1, len(sp))).round(0)
sp.loc[sp.acquisition_channel == "Organic", "spend_usd"] = 600.0          # app-store listing + content, flat
sp = sp.drop(columns="signups").rename(columns={"acquisition_channel": "channel"})

U.to_csv(OUT / "users.csv", index=False)
T.to_csv(OUT / "transactions.csv", index=False)
sp.to_csv(OUT / "marketing_spend.csv", index=False)
print({"users": len(U), "transactions": len(T), "spend_rows": len(sp)})
