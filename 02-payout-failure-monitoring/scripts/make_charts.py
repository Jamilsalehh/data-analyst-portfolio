"""README charts for the payout failure project (computed from ./data)."""
import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "_tools"))
from charts import style, save, ACCENT, ACCENT2, BAD, MUTED, INK  # noqa: E402

IMG = ROOT / "images"; IMG.mkdir(exist_ok=True)
D = ROOT / "data"
p = pd.read_csv(D / "payouts.csv", dtype={"response_code": str}, parse_dates=["received_time"]).drop_duplicates()
p["status"] = p.status.str.upper()
tax = pd.read_csv(D / "error_taxonomy.csv", dtype={"response_code": str})
p = p.merge(tax, on="response_code", how="left")
fail = p[p.status == "FAILED"]

# 1) failures by category, coloured by owner
cat = fail.groupby(["failure_category", "owner"]).size().reset_index(name="n").sort_values("n")
fig, ax = plt.subplots(figsize=(8, 3.8))
colors = [BAD if c == "Receiver details" else ACCENT2 for c in cat.failure_category]
ax.barh(cat.failure_category + "  (" + cat.owner + ")", cat.n, color=colors, height=0.6)
tot = cat.n.sum()
for i, v in enumerate(cat.n):
    ax.text(v + 40, i, f"{v:,}  ·  {v / tot:.0%}", va="center", fontsize=9, color=INK)
ax.set_xlim(0, cat.n.max() * 1.25)
ax.grid(axis="x", color="#e6e9ee"); ax.grid(axis="y", visible=False)
style(ax, "6 in 10 failed payouts come down to wrong receiver details", "Failed payout attempts by failure category (team that owns the fix), Apr–Sep 2026")
ax.grid(axis="y", visible=False)
save(fig, IMG / "failures_by_category.png")

# 2) retries: blind vs sensible
orig = p[["partner_txn_id", "response_code"]].rename(columns={"partner_txn_id": "retry_of", "response_code": "orig_code"})
r = p[p.retry_of.notna()].merge(orig, on="retry_of").merge(
    tax[["response_code", "retry_recommended"]].rename(columns={"response_code": "orig_code", "retry_recommended": "orig_retryable"}), on="orig_code")
g = r.groupby("orig_retryable").agg(n=("status", "size"), ok=("status", lambda s: (s == "SUCCESS").mean() * 100))
lab = {"No": "Retried after a\nnon-retryable error", "Yes": "Retried after a\nretryable error (timeout, outage)"}
fig, ax = plt.subplots(figsize=(7, 3.8))
ax.bar([lab[i] for i in g.index], g.ok, color=[BAD, ACCENT], width=0.55)
for i, (n, v) in enumerate(zip(g.n, g.ok)):
    ax.text(i, v + 2, f"{v:.0f}% succeeded\n({n:,} retries)", ha="center", fontsize=9, color=INK)
ax.set_ylim(0, 110)
style(ax, "3 in 4 retries were on errors a retry can't fix", "Success rate of retried payouts, by whether the original error is retryable")
save(fig, IMG / "retries.png")

# 3) prefunding failures by day of month
f01 = fail[fail.response_code == "F01"]
dom = f01.received_time.dt.day.value_counts().reindex(range(1, 32), fill_value=0)
fig, ax = plt.subplots(figsize=(8, 3.4))
ax.bar(dom.index, dom.values, color=[BAD if d >= 27 else ACCENT2 for d in dom.index], width=0.7)
ax.set_xticks(range(1, 32, 2))
ax.set_xlabel("Day of month", color=MUTED, fontsize=9)
style(ax, "'Insufficient prefunding' failures only happen at month-end", "Payouts failed because the partner account ran low, by day of month (Apr–Sep 2026)")
save(fig, IMG / "prefunding_by_day.png")
print("charts written to", IMG)
