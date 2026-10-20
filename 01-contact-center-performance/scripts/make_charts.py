"""README charts for the Contact Center project (computed from ./data)."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "_tools"))
from charts import style, save, ACCENT, ACCENT2, BAD, MUTED, INK  # noqa: E402

IMG = ROOT / "images"
IMG.mkdir(exist_ok=True)
q = pd.read_csv(ROOT / "data/calls_queue_hourly.csv", parse_dates=["call_date"])
a = pd.read_csv(ROOT / "data/calls_agent_daily.csv", parse_dates=["work_date"]).drop_duplicates()
t = pd.read_csv(ROOT / "data/tickets.csv", parse_dates=["created_at", "first_reply_at", "solved_at"])

# 1) App Support answer rate vs agents on the team
app = q[q.queue == "App Support"].copy()
app["m"] = app.call_date.dt.to_period("M")
m = app.groupby("m")[["offered", "answered"]].sum()
m["ar"] = m.answered / m.offered * 100
wk = a[(a.queue == "App Support") & (a.work_date.dt.dayofweek < 5)]
hc = wk.groupby("work_date").agent_id.nunique().groupby(lambda d: d.to_period("M")).mean()
fig, ax = plt.subplots(figsize=(8, 4))
x = [p.strftime("%b") for p in m.index]
ax.bar(x, hc.reindex(m.index).values, color="#dbe4f3", width=0.6, label="Agents on App Support phones")
for xi, v in zip(x, hc.reindex(m.index).values):
    ax.text(xi, v / 2, f"{v:.0f}", ha="center", fontsize=8.5, color=MUTED)
ax.set_ylim(0, 32)
ax.set_ylabel("Avg agents on the phones per weekday", color=MUTED, fontsize=9)
ax2 = ax.twinx()
ax2.plot(x, m.ar.values, color=ACCENT, marker="o", lw=2.4, label="Answer rate %")
for xi, v in zip(x, m.ar.values):
    ax2.annotate(f"{v:.0f}%", (xi, v), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8.5, color=INK)
ax2.set_ylim(60, 95)
ax2.spines["top"].set_visible(False); ax2.spines["right"].set_visible(False); ax2.tick_params(colors=MUTED, labelsize=9)
style(ax, "App Support answer rate fell when the team shrank", "Monthly answer rate (line) vs. average agents on App Support phones per weekday (bars), 2026")
save(fig, IMG / "answer_rate_vs_headcount.png")

# 2) Abandon-rate heatmap weekday x hour (App Support)
app["wd"] = app.call_date.dt.dayofweek
hm = app.groupby(["wd", "call_hour"])[["offered", "abandoned"]].sum()
hm = (hm.abandoned / hm.offered * 100).unstack()
fig, ax = plt.subplots(figsize=(8.5, 3.6))
im = ax.imshow(hm.values, cmap="Reds", aspect="auto", vmin=0, vmax=45)
ax.set_yticks(range(7), ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
ax.set_xticks(range(len(hm.columns)), [f"{h}:00" for h in hm.columns], rotation=0, fontsize=8)
for i in range(hm.shape[0]):
    for j in range(hm.shape[1]):
        v = hm.values[i, j]
        ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=7.5, color="white" if v > 25 else INK)
style(ax, "Callers give up most at lunchtime, especially on Mondays", "App Support abandon rate %, by weekday and hour (Jan–Sep 2026)")
ax.grid(False)
save(fig, IMG / "abandon_heatmap.png")

# 3) CSAT by first-reply time
t = t[t.solved_at.isna() | (t.solved_at >= t.created_at)]
t["frt"] = (t.first_reply_at - t.created_at).dt.total_seconds() / 60
b = pd.cut(t.frt, [0, 60, 120, 240, 480, np.inf], labels=["< 1h", "1–2h", "2–4h", "4–8h", "> 8h"])
r = t[t.satisfaction.notna()].assign(b=b).groupby("b", observed=True).satisfaction.apply(lambda s: (s == "good").mean() * 100)
fig, ax = plt.subplots(figsize=(7, 3.8))
cols = [ACCENT if v >= 80 else BAD for v in r.values]
ax.bar(r.index.astype(str), r.values, color=cols, width=0.6)
for i, v in enumerate(r.values):
    ax.text(i, v + 1.5, f"{v:.0f}%", ha="center", fontsize=9, color=INK)
ax.set_ylim(0, 105)
ax.set_xlabel("Time to first reply", color=MUTED, fontsize=9)
style(ax, "Satisfaction drops sharply once a first reply takes over 4 hours", "Share of rated tickets marked 'good', by time to first reply")
save(fig, IMG / "csat_by_first_reply.png")
print("charts written to", IMG)
