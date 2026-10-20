"""README numbers and charts for the QA project, read from the recalculated SAMPLE workbook."""
import json, sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "_tools"))
from charts import style, save, ACCENT, ACCENT2, BAD, MUTED, INK  # noqa: E402

IMG = ROOT / "images"; IMG.mkdir(exist_ok=True)
x = pd.read_excel(ROOT / "data/QA_Audit_Log_SAMPLE.xlsx", sheet_name="Audits")
rub = pd.read_csv(ROOT / "data/rubric.csv")
x["auto"] = x.audit_ts >= "2026-07-01"
x["period"] = x.auto.map({False: "Apr–Jun (manual)", True: "Jul–Sep (automated)"})
x["m"] = x.audit_ts.dt.to_period("M")
out = {"audits": len(x), "agents": int(x.agent_id.nunique()), "critical_errors": int(x.critical_error.sum())}

g = x.groupby("period")
out["by_period"] = pd.DataFrame({
    "audits": g.size(),
    "avg_score": g.score.mean().round(1),
    "below_70_pct": g.score.apply(lambda s: (s < 70).mean() * 100).round(1),
    "median_hours_to_feedback": g.hours_to_feedback.median().round(2),
    "median_hours_to_ack": g.apply(lambda d: ((d.agent_acknowledged_at - d.feedback_sent_at).dt.total_seconds() / 3600).median()).round(1),
}).reset_index().to_dict("records")
out["monthly"] = x.groupby("m").agg(avg=("score", "mean"), below70=("score", lambda s: (s < 70).mean() * 100)).round(1).reset_index().astype(str).to_dict("records")

# what happens on the next audit after a score under 70?
x = x.sort_values(["agent_id", "audit_ts"])
x["next_score"] = x.groupby("agent_id").score.shift(-1)
low = x[(x.score < 70) & x.next_score.notna()]
out["next_audit_gain_after_sub70"] = low.groupby("period").apply(lambda d: round((d.next_score - d.score).mean(), 1)).to_dict()
out["next_audit_back_to_70_pct"] = low.groupby("period").apply(lambda d: round((d.next_score >= 70).mean() * 100, 1)).to_dict()

# repeat failures: the same criterion scored <=2 on two audits in a row for the same agent
crit = [f"c{i}_score" for i in range(1, 7)]
rep = []
for _, d in x.groupby("agent_id"):
    d = d.reset_index(drop=True)
    for i in range(len(d) - 1):
        for c in crit:
            if d.loc[i, c] <= 2:
                rep.append((d.loc[i, "period"], d.loc[i + 1, c] <= 2))
rep = pd.DataFrame(rep, columns=["period", "repeated"])
out["repeat_failure_pct"] = (rep.groupby("period").repeated.mean() * 100).round(1).to_dict()

# most failed criteria
fails = {rub.criterion[i]: int((x[c] <= 2).sum()) for i, c in enumerate(crit)}
out["criterion_fail_counts"] = dict(sorted(fails.items(), key=lambda kv: -kv[1]))
ag = x.groupby(["agent_id", "period"]).score.mean().unstack()
out["agents_up_5plus"] = int(((ag.iloc[:, 1] - ag.iloc[:, 0]) >= 5).sum())
out["agents_down"] = int(((ag.iloc[:, 1] - ag.iloc[:, 0]) < 0).sum())
print(json.dumps(out, indent=1, default=str))
json.dump(out, open(ROOT / "scripts/expected_numbers.json", "w"), indent=1, default=str)

# ---- chart 1: monthly share of audits under 70 + avg score
m = x.groupby("m").agg(avg=("score", "mean"), below=("score", lambda s: (s < 70).mean() * 100))
fig, ax = plt.subplots(figsize=(8, 3.6))
lbl = [p.strftime("%b") for p in m.index]
ax.bar(lbl, m.below, color=[ACCENT2 if p.month < 7 else ACCENT for p in m.index], width=0.55)
for i, v in enumerate(m.below):
    ax.text(i, v + 0.6, f"{v:.0f}%", ha="center", fontsize=9, color=INK)
ax.axvline(2.5, color=INK, ls="--", lw=1)
ax.text(2.6, m.below.max() * 0.95, "Forms + Power Automate\nfeedback goes live", fontsize=8.5, color=INK)
ax.set_ylim(0, m.below.max() * 1.25)
style(ax, "Fewer audits under 70 once feedback became instant", "Share of QA audits below 70 points, by month (2026)")
save(fig, IMG / "below70_by_month.png")

# ---- chart 2: time to feedback
x["fb_hours_exact"] = (x.feedback_sent_at - x.audit_ts).dt.total_seconds() / 3600
fb = x.groupby("period").fb_hours_exact.median()
out["median_minutes_to_feedback"] = (fb * 60).round(1).to_dict()
json.dump(out, open(ROOT / "scripts/expected_numbers.json", "w"), indent=1, default=str)
fig, ax = plt.subplots(figsize=(7, 3))
ax.barh(fb.index, fb.values, color=[ACCENT2, ACCENT], height=0.5)
for i, v in enumerate(fb.values):
    ax.text(v + 2, i, f"{v / 24:.1f} days" if v > 24 else f"{v * 60:.0f} minutes", va="center", fontsize=10, color=INK)
ax.set_xlim(0, fb.max() * 1.3)
ax.set_xlabel("Median hours from audit to feedback in the agent's inbox", color=MUTED, fontsize=9)
style(ax, f"From {fb.iloc[0] / 24:.0f} days to {fb.iloc[1] * 60:.0f} minutes", "Median time between a QA audit and the agent receiving feedback")
ax.grid(axis="y", visible=False); ax.grid(axis="x", color="#e6e9ee")
save(fig, IMG / "time_to_feedback.png")
# ---- chart 3: repeat failures
rp = rep.groupby("period").repeated.mean() * 100
fig, ax = plt.subplots(figsize=(7, 3.4))
ax.bar(rp.index, rp.values, color=[ACCENT2, ACCENT], width=0.5)
for i, v in enumerate(rp.values):
    ax.text(i, v + 1.5, f"{v:.0f}%", ha="center", fontsize=11, color=INK, fontweight="bold")
ax.set_ylim(0, 60)
style(ax, "Agents stopped repeating the same mistake", "When a criterion scored 2/5 or less, how often it failed again on the agent's next audit")
save(fig, IMG / "repeat_failures.png")
print("charts written")
