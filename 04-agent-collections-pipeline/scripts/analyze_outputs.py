"""Numbers and charts for the README, computed from the pipeline's own output sheets (tests/output)."""
import json, sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "_tools"))
from charts import style, save, ACCENT, ACCENT2, BAD, MUTED, INK  # noqa: E402

O = ROOT / "tests/output"
IMG = ROOT / "images"; IMG.mkdir(exist_ok=True)
f = pd.read_csv(O / "FCT_PAYMENTS.csv", parse_dates=["txn_date"])
dim = pd.read_csv(O / "DIM_AGENT.csv")
sales = pd.read_csv(O / "FCT_POLICY_SALES.csv")
out = {}
out["payments"] = len(f)
out["total_usd"] = round(f.amount_usd.sum())
out["active_agents"] = int(f.agent_code.nunique())
out["avg_payment"] = round(f.amount_usd.mean(), 2)
out["avg_payments_per_day"] = round(len(f) / f.txn_date.nunique())
out["policies_sold"] = len(sales)
out["premium_usd"] = round(sales.premium_usd.sum())

# concentration
top = dim.sort_values("amount_usd", ascending=False)
out["top50_share_pct"] = round(top.head(50).amount_usd.sum() / top.amount_usd.sum() * 100, 1)
out["agents_for_half_of_usd"] = int((top.amount_usd.cumsum() / top.amount_usd.sum() < 0.5).sum() + 1)
net = f.groupby("agent_network").agg(agents=("agent_code", "nunique"), payments=("txn_key", "size"), usd=("amount_usd", "sum"),
                                     same_day=("bought_here_same_day", "mean"))
net["share_usd_pct"] = (net.usd / net.usd.sum() * 100).round(1)
net["same_day_pct"] = (net.same_day * 100).round(1)
out["by_network"] = net[["agents", "payments", "usd", "share_usd_pct", "same_day_pct"]].reset_index().to_dict("records")

# cross-sell opportunity: regular agents at the sub-agent rate, and at the branch rate
reg = net.loc["Regular agents"]
avg_prem = sales.premium_usd.mean()
COMMISSION = 0.16
for target in ("Sub-agents", "Company branches"):
    extra = reg.payments * (net.loc[target, "same_day"] - reg.same_day)
    out[f"extra_policies_if_regular_at_{target}"] = int(round(extra))
    out[f"extra_commission_usd_if_regular_at_{target}"] = int(round(extra * avg_prem * COMMISSION))
out["avg_premium"] = round(avg_prem, 2)

# timing
f["dom"] = f.txn_date.dt.day
out["avg_daily_usd_day1_23"] = round(f[f.dom < 24].groupby("txn_date").amount_usd.sum().mean())
out["avg_daily_usd_day24_end"] = round(f[f.dom >= 24].groupby("txn_date").amount_usd.sum().mean())
wd = f.groupby([f.txn_date.dt.day_name(), "txn_date"]).size().groupby(level=0).mean().round(0)
out["avg_payments_by_weekday"] = wd.to_dict()

# data quality
flags = f.dq_flags.dropna().str.split("|").explode().value_counts()
out["flagged_payments"] = int((f.dq_status == "review").sum())
out["passed_checks_pct"] = round((f.dq_status == "ok").mean() * 100, 2)
out["flags"] = flags.to_dict()
ph = f[f.dq_flags.fillna("").str.contains("placeholder_policy")]
by_agent = ph.agent_name.value_counts()
out["placeholder_top8_agents_share_pct"] = round(by_agent.head(8).sum() / len(ph) * 100, 1)
out["placeholder_total"] = len(ph)
print(json.dumps(out, indent=1, default=str))
json.dump(out, open(ROOT / "scripts/expected_numbers.json", "w"), indent=1, default=str)

# ---- charts
n2 = net.sort_values("same_day_pct")
fig, ax = plt.subplots(figsize=(8, 3.6))
cols = [BAD if i == "Regular agents" else ACCENT2 for i in n2.index]
ax.barh(n2.index, n2.same_day_pct, color=cols, height=0.55)
for i, (v, s) in enumerate(zip(n2.same_day_pct, n2.share_usd_pct)):
    ax.text(v + 1, i, f"{v:.0f}%   ({s:.0f}% of collections)", va="center", fontsize=9, color=INK)
ax.set_xlim(0, 110)
style(ax, "Regular agents rarely sell the insurance with the fee", "Share of fee payments where the customer bought the policy at the same agent, same day")
ax.grid(axis="y", visible=False); ax.grid(axis="x", color="#e6e9ee")
save(fig, IMG / "same_day_policy_by_network.png")

daily = f.groupby("txn_date").amount_usd.sum()
fig, ax = plt.subplots(figsize=(8.5, 3.4))
ax.fill_between(daily.index, daily.values, color="#dbe4f3")
ax.plot(daily.index, daily.values, color=ACCENT, lw=1.6)
for m in pd.date_range("2026-07-24", "2026-09-30", freq="MS").union(pd.to_datetime(["2026-07-24", "2026-08-24", "2026-09-24"])):
    if m.day == 24:
        ax.axvspan(m, m + pd.offsets.MonthEnd(0) + pd.Timedelta(days=1), color=BAD, alpha=0.07)
ax.set_ylabel("USD collected per day", color=MUTED, fontsize=9)
style(ax, "Collections jump in the last week of every month", "Daily fee collections (USD). Shaded: 24th to month-end. Sunday dips are agents closing.")
save(fig, IMG / "daily_collections.png")
print("charts written")
