"""README charts for the wallet retention project, drawn from the SQL results (run via _tools/run_bq_sql.py --json)."""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "_tools"))
from charts import style, save, ACCENT, ACCENT2, BAD, MUTED, INK  # noqa: E402

IMG = ROOT / "images"; IMG.mkdir(exist_ok=True)
R = json.load(open(sys.argv[1]))

# 1) cohort heatmap
c = pd.DataFrame(R["02_cohort_retention.sql#1"])
c["cohort"] = pd.to_datetime(c.cohort_month).dt.strftime("%b %y")
order = pd.to_datetime(c.cohort_month).drop_duplicates().sort_values().dt.strftime("%b %y")
hm = c.pivot(index="cohort", columns="month_number", values="retention_pct").reindex(order)[list(range(0, 9))]
sizes = c.drop_duplicates("cohort").set_index("cohort").cohort_size.reindex(order)
fig, ax = plt.subplots(figsize=(9, 4.6))
ax.imshow(hm.values, cmap="Blues", aspect="auto", vmin=20, vmax=100)
for i in range(hm.shape[0]):
    for j in range(hm.shape[1]):
        v = hm.values[i, j]
        if not np.isnan(v):
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=8, color="white" if v > 62 else INK)
ax.set_yticks(range(len(order)), [f"{o}  (n={s:,})" for o, s in zip(order, sizes)], fontsize=8.5)
ax.set_xticks(range(hm.shape[1]), [f"M{j}" for j in hm.columns], fontsize=8.5)
for i, o in enumerate(order):
    if o in ("Jan 26", "Feb 26", "Mar 26"):
        ax.add_patch(plt.Rectangle((-0.5, i - 0.5), hm.shape[1], 1, fill=False, ec=BAD, lw=1.4))
style(ax, "The paid-push cohorts (Jan–Mar) keep fewer users", "% of each signup cohort making a completed transaction N months after signup. Red boxes: social ads + cashback push")
ax.grid(False)
save(fig, IMG / "cohort_heatmap.png")

# 2) M3 retention by channel, activated vs not
a = pd.DataFrame(R["03_channels_and_activation.sql#2"]).set_index("acquisition_channel")
order2 = ["Referral", "Agent onboarding", "Organic", "Social ads", "Cashback promo"]
a = a.reindex(order2)
x = np.arange(len(a)); w = 0.38
fig, ax = plt.subplots(figsize=(8.5, 3.8))
ax.bar(x - w / 2, a.m3_if_activated_pct, w, color=ACCENT, label="Paid a bill or merchant in first 14 days")
ax.bar(x + w / 2, a.m3_if_not_activated_pct, w, color=ACCENT2, label="Didn't")
for i, (p, q) in enumerate(zip(a.m3_if_activated_pct, a.m3_if_not_activated_pct)):
    ax.text(i - w / 2, p + 1.5, f"{p:.0f}%", ha="center", fontsize=8.5, color=INK)
    ax.text(i + w / 2, q + 1.5, f"{q:.0f}%", ha="center", fontsize=8.5, color=INK)
ax.set_xticks(x, order2)
ax.set_ylim(0, 100)
ax.legend(frameon=False, fontsize=8.5, loc="upper right")
style(ax, "Users who pay a bill early stay, in every channel", "Month-3 retention by acquisition channel (cohorts Oct 2025 – Jun 2026)")
save(fig, IMG / "activation_by_channel.png")

# 3) CAC vs 6-month revenue
p = pd.DataFrame(R["04_payback_by_channel.sql#1"]).set_index("channel").reindex(order2)
fig, ax = plt.subplots(figsize=(8.5, 3.8))
ax.bar(x - w / 2, p.cac_usd, w, color=BAD, label="Cost to acquire a user (CAC)")
ax.bar(x + w / 2, p.revenue_per_user_6m_usd, w, color=ACCENT, label="Fee revenue per user, first 6 months")
for i, (c1, r1) in enumerate(zip(p.cac_usd, p.revenue_per_user_6m_usd)):
    ax.text(i - w / 2, c1 + 0.3, f"${c1:.2f}", ha="center", fontsize=8.5, color=INK)
    ax.text(i + w / 2, r1 + 0.3, f"${r1:.2f}", ha="center", fontsize=8.5, color=INK)
ax.set_xticks(x, order2)
ax.legend(frameon=False, fontsize=8.5, loc="upper center")
ax.set_ylim(0, max(p.cac_usd.max(), p.revenue_per_user_6m_usd.max()) * 1.3)
style(ax, r"Social ads cost \$11 a user and earn back less than \$5", "CAC vs. 6-month fee revenue per user, cohorts Oct 2025 – Mar 2026")
save(fig, IMG / "cac_vs_revenue.png")
print("charts written")
