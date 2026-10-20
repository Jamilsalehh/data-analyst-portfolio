"""
Synthetic raw exports for the Agent-Network Collections Pipeline.

Northwind Pay (fictional) collects a yearly vehicle inspection fee through
~1,000 retail agent locations, and its agents also sell compulsory car
insurance on behalf of four partner insurers. Two raw exports arrive:
  * payments  - one row per fee payment (messy, like a real agent-system export)
  * policy sales - one row per insurance policy sold at a Northwind agent
Everything is generated. Output: data/raw/payments_YYYY-MM.csv and
data/raw/policy_sales_YYYY-MM.csv for Jul, Aug, Sep 2026.
"""
import numpy as np
import pandas as pd
from pathlib import Path

rng = np.random.default_rng(20260704)
OUT = Path(__file__).resolve().parents[1] / "data" / "raw"
OUT.mkdir(parents=True, exist_ok=True)
START, END = pd.Timestamp("2026-07-01"), pd.Timestamp("2026-09-30")
LBP_PER_USD = 89_500
FEE_USD = [25, 35, 45, 60]                 # fee depends on vehicle category
FEE_P = [0.15, 0.55, 0.22, 0.08]

NETWORKS = {  # name, agents, activity weight, chance a customer buys the policy here the same day
    "Company branches": (30, 9.0, 0.76),
    "Partner chain A": (14, 6.0, 0.72),
    "Partner chain B": (8, 5.0, 0.68),
    "Sub-agents": (45, 1.6, 0.47),
    "Regular agents": (900, 1.0, 0.29),
}
INSURERS = {"Insurer A": (0.42, ["Insurer A", "INSURER A S.A.L", "insurer a", "Ins. A"]),
            "Insurer B": (0.26, ["Insurer B", "INSURER B", "Insurer B s.a.l."]),
            "Insurer C": (0.22, ["Insurer C", "INSURER C SAL", "insurer-c"]),
            "Insurer D": (0.10, ["Insurer D", "INSURER D"])}
TOWNS = ["Hamra", "Achrafieh", "Jounieh", "Tripoli", "Saida", "Zahle", "Tyre", "Byblos", "Aley", "Baabda",
         "Dekwaneh", "Nabatieh", "Batroun", "Chtaura", "Verdun", "Mazraa", "Jdeideh", "Antelias", "Halba", "Baalbek"]
WORDS = ["Cedar", "Star", "Golden", "Hope", "Unity", "Nour", "Rainbow", "Sunrise", "Atlas", "Phoenix", "Royal", "Prime",
         "Al Amal", "Express", "City", "Smart", "Family", "Bright", "Mountain", "Coast"]
KINDS = ["Services", "Trading", "Mobile Shop", "Exchange", "Pharmacy", "Market", "Bookshop", "Telecom"]

agents, n = [], 1
for net, (k, w, _) in NETWORKS.items():
    for i in range(k):
        town = rng.choice(TOWNS)
        if net == "Company branches":
            name = f"NORTHWIND - {town.upper()}" + (f" {i // len(TOWNS) + 2}" if i >= len(TOWNS) else "")
        elif net.startswith("Partner chain"):
            name = f"{'ALPHA' if net.endswith('A') else 'BETA'} SAL - {town.upper()}"
        else:
            name = f"{rng.choice(WORDS).upper()} {rng.choice(KINDS).upper()} - {town.upper()}"
        agents.append(dict(agent_code=f"AG{n:05d}", agent_name=name, network=net, weight=w * rng.lognormal(0, 0.9)))
        n += 1
AG = pd.DataFrame(agents).drop_duplicates("agent_name").reset_index(drop=True)
AG["p"] = AG.weight / AG.weight.sum()
SAME_DAY = {k: v[2] for k, v in NETWORKS.items()}
# a handful of busy regular agents type placeholders instead of real policy numbers
SLOPPY = set(AG[AG.network == "Regular agents"].sort_values("weight", ascending=False).index[5:13])
ins_names = list(INSURERS); ins_p = [v[0] for v in INSURERS.values()]

pay_rows, sale_rows = [], []
ref, sale_id, pol = 5_000_000, 800_000, 1_000_000
for day in pd.date_range(START, END, freq="D"):
    if day.weekday() == 6:
        base = 70                      # most agents closed on Sunday
    else:
        base = 300 * (1.25 if day.weekday() in (0, 1) else 1.0)
    base *= 1 + 0.6 * (day.day >= 24)  # month-end rush before the inspection deadline
    n_pay = rng.poisson(base)
    picks = rng.choice(len(AG), n_pay, p=AG.p)
    for a in picks:
        ag = AG.iloc[a]
        hour = int(np.clip(rng.normal(12.5, 2.6), 7, 20))
        ts = day + pd.Timedelta(hours=hour, minutes=int(rng.integers(60)))
        fee = rng.choice(FEE_USD, p=FEE_P)
        insurer = rng.choice(ins_names, p=ins_p)
        bought_here = rng.random() < SAME_DAY[ag.network]
        pol += 1
        policy_no = f"P{pol}"
        if bought_here:
            inception = day
            sale_id += 1
            premium = round(float(rng.normal(42, 6)), 2)
            sale_rows.append({"Sale Date": (ts - pd.Timedelta(minutes=int(rng.integers(5, 40)))).strftime("%d/%m/%Y %H:%M"),
                              "Sale ID": f"S{sale_id}", "Partner": insurer, "Agent Name": ag.agent_name,
                              "Policy No": policy_no, "Policy Type": "Compulsory", "Premium (USD)": premium})
        else:
            inception = day - pd.Timedelta(days=int(rng.choice([0, 1, 2, 5, 12, 30, 60, 120], p=[.35, .15, .1, .1, .1, .1, .05, .05])))
        expiry = inception + pd.Timedelta(days=365)
        row = {"Txn Date": ts.strftime("%d/%m/%Y %H:%M"), "Reference": f"R{ref}", "Agent Code": ag.agent_code,
               "Agent Name": ag.agent_name, "Agent Category": ag.network,
               "Amount (LBP)": f"{int(fee * LBP_PER_USD):,}", "Insurer": rng.choice(INSURERS[insurer][1]),
               "Policy No": policy_no, "Inception Date": inception.strftime("%d/%m/%Y"),
               "Expiry Date": expiry.strftime("%d/%m/%Y")}
        ref += 1
        # ---- data problems seen in real exports (each one is a DQ check in the pipeline)
        r = rng.random()
        if a in SLOPPY and rng.random() < 0.10:
            row["Policy No"] = rng.choice(["0", "N/A", "123", "-"])
        elif r < 0.006:
            row["Policy No"] = rng.choice(["0", "N/A", "123", "-"])                       # placeholder policy number
        elif r < 0.017:
            row["Expiry Date"] = (inception + pd.Timedelta(days=int(rng.choice([3, 30, 900])))).strftime("%d/%m/%Y")  # odd term
        elif r < 0.020:
            row["Insurer"] = ""                                                           # insurer missing
        elif r < 0.022:
            row["Inception Date"] = ""; row["Expiry Date"] = ""                           # policy details missing
        pay_rows.append(row)

P = pd.DataFrame(pay_rows)
S = pd.DataFrame(sale_rows)
# the export sometimes repeats rows when an agent's terminal re-syncs
dups = P.sample(140, random_state=4)
P = pd.concat([P, dups]).reset_index(drop=True)
P["_d"] = pd.to_datetime(P["Txn Date"], format="%d/%m/%Y %H:%M")
P = P.sort_values("_d")
S["_d"] = pd.to_datetime(S["Sale Date"], format="%d/%m/%Y %H:%M")
for m in ("2026-07", "2026-08", "2026-09"):
    P[P._d.dt.strftime("%Y-%m") == m].drop(columns="_d").to_csv(OUT / f"payments_{m}.csv", index=False)
    S[S._d.dt.strftime("%Y-%m") == m].drop(columns="_d").to_csv(OUT / f"policy_sales_{m}.csv", index=False)
print({"payments": len(P), "policy_sales": len(S), "agents": len(AG)})
