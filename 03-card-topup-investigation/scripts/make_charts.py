"""README charts for the card top-up investigation (computed from ./data)."""
import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "_tools"))
from charts import style, save, ACCENT, ACCENT2, BAD, MUTED, INK  # noqa: E402

IMG = ROOT / "images"; IMG.mkdir(exist_ok=True)
a = pd.read_csv(ROOT / "data/topup_attempts.csv", parse_dates=["attempted_at"]).drop_duplicates("attempt_id")
a["ok"] = a.status == "ACCEPTED"
a["d"] = a.attempted_at.dt.floor("D")
a["grp"] = (a.issuer == "Issuer 03").map({True: "Issuer 03", False: "All other issuers"})

# 1) daily acceptance, 7-day rolling
d = a.groupby(["d", "grp"]).ok.mean().unstack() * 100
d = d.rolling(3, min_periods=1).mean()
fig, ax = plt.subplots(figsize=(8.5, 3.8))
ax.plot(d.index, d["All other issuers"], color=ACCENT2, lw=2, label="All other issuers")
ax.plot(d.index, d["Issuer 03"], color=BAD, lw=2.4, label="Issuer 03")
ax.axvline(pd.Timestamp("2026-08-25"), color=INK, lw=1, ls="--")
ax.text(pd.Timestamp("2026-08-26"), 50, "25 Aug, ~09:40\nIssuer 03 cards stop\nworking on every gateway", fontsize=8.5, color=INK)
ax.set_ylim(-3, 100)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
ax.legend(frameon=False, fontsize=9, loc="lower left")
style(ax, "One issuer's cards went from 85% accepted to zero overnight", "Card top-up acceptance rate %, 3-day rolling average, Jul–Oct 2026")
save(fig, IMG / "acceptance_timeline.png")

# 2) failure reasons by gateway after the break (Issuer 03)
b = a[(a.issuer == "Issuer 03") & (a.attempted_at >= "2026-08-25 09:40")]
ct = pd.crosstab(b.gateway, b.failure_reason)
order = ct.sum().sort_values(ascending=False).index
ct = ct[order]
fig, ax = plt.subplots(figsize=(8.5, 3.4))
palette = ["#b91c1c", "#ef4444", "#f87171", "#fca5a5", "#fecaca"]
left = pd.Series(0, index=ct.index)
for col, colr in zip(ct.columns, palette):
    ax.barh(ct.index, ct[col], left=left, color=colr, label=col, height=0.55)
    left += ct[col]
for i, (g, tot) in enumerate(ct.sum(axis=1).items()):
    ax.text(tot + 20, i, f"{tot:,} attempts · 0 accepted", va="center", fontsize=9, color=INK)
ax.set_xlim(0, ct.sum(axis=1).max() * 1.75)
ax.invert_yaxis()
ax.legend(frameon=False, fontsize=8, ncol=1, loc="lower right")
style(ax, "Three gateways, five different error messages, one result", "Issuer 03 top-up attempts after the break, by gateway and the reason each gateway returned")
ax.grid(axis="y", visible=False); ax.grid(axis="x", color="#e6e9ee")
save(fig, IMG / "reasons_by_gateway.png")
print("charts written to", IMG)
