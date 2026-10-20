"""
Synthetic QA audit data for the QA Scorecard Automation project.

Northwind Pay (fictional) audits support interactions (calls, tickets, chats)
against a weighted 6-criterion rubric. Until 30 Jun 2026 audits lived in
per-agent spreadsheet tabs and feedback went out by hand; from 1 Jul a
Microsoft Forms -> Power Automate flow scores each audit and emails the
agent the same day. Everything here is generated.
"""
import numpy as np
import pandas as pd
from pathlib import Path

rng = np.random.default_rng(20260701)
OUT = Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(exist_ok=True)
AUTOMATION_START = pd.Timestamp("2026-07-01")

RUBRIC = [  # id, criterion, weight, what it measures
    ("c1", "Communication", 15, "Greeting, empathy, clear language, proper closing"),
    ("c2", "Issue handling & SOP", 25, "Understood the issue and followed the correct procedure"),
    ("c3", "Resolution & follow-up", 20, "Solved it, or set a clear next step and followed up on time"),
    ("c4", "Escalation & ownership", 15, "Escalated only when needed, with complete notes; owned the case"),
    ("c5", "Accuracy & documentation", 10, "Information given was correct; ticket/call notes complete"),
    ("c6", "Security & compliance", 15, "Verified identity before account changes; no data shared wrongly"),
]
BANDS = [(90, "Outstanding"), (80, "Solid Performance"), (70, "Meets Expectations"), (60, "Needs Improvement"), (0, "Critical")]
FIRST = ["Rami", "Lina", "Karim", "Maya", "Omar", "Nour", "Hadi", "Rana", "Ziad", "Sara", "Fadi", "Dana", "Tarek", "Yara",
         "Samir", "Hiba", "Jad", "Rita", "Walid", "Lara", "Bilal", "Mira", "Nabil", "Joelle", "Sami", "Layal", "Firas",
         "Reem", "Ali", "Nadine", "Elie", "Hala", "Majd", "Tala", "Imad", "Celine", "Rabih", "Aya", "Ghassan", "Zeina"]
LAST = ["Haddad", "Khoury", "Nassar", "Saab", "Aoun", "Hajj", "Daher", "Karam", "Fares", "Mansour", "Salem", "Hamdan",
        "Bitar", "Rizk", "Sleiman", "Ghanem", "Harb", "Najjar", "Chami", "Yazbek"]

teams = ["After-Sales"] * 22 + ["Agent Support"] * 10 + ["Card Services"] * 8
agents = []
for i, t in enumerate(teams):
    agents.append(dict(agent_id=f"QA{i + 1:03d}", agent_name=f"{FIRST[i]} {rng.choice(LAST)}", team=t,
                       team_lead={"After-Sales": "Lead · After-Sales", "Agent Support": "Lead · Agent Support",
                                  "Card Services": "Lead · Card Services"}[t],
                       skill=float(rng.normal(0, 0.55))))
AG = pd.DataFrame(agents)
# each agent has one weak criterion they keep repeating
AG["weak"] = rng.choice([r[0] for r in RUBRIC], len(AG), p=[0.15, 0.30, 0.25, 0.12, 0.10, 0.08])
REVIEWERS = ["QA Reviewer 1", "QA Reviewer 2", "QA Reviewer 3"]
CHANNEL = {"After-Sales": (["Call", "Ticket", "Chat"], [0.45, 0.40, 0.15]),
           "Agent Support": (["Call", "Ticket", "Chat"], [0.55, 0.30, 0.15]),
           "Card Services": (["Call", "Ticket", "Chat"], [0.25, 0.65, 0.10])}
FLAG_TEXT = {"c1": "Rushed greeting / no empathy statement", "c2": "Skipped a step in the SOP",
             "c3": "No follow-up after promising a callback", "c4": "Escalated without full notes",
             "c5": "Gave wrong fee / timing information", "c6": "Changed account details before verifying identity"}

rows, aid = [], 70001
days = pd.bdate_range("2026-04-01", "2026-09-30")
state = {a: {"weak_level": 2.0, "pending": 0.0} for a in AG.agent_id}
for day in days:
    automated = day >= AUTOMATION_START
    # ~4 audits per reviewer per working day
    for a_idx in rng.choice(len(AG), 12, replace=False):
        ag = AG.iloc[a_idx]
        st = state[ag.agent_id]
        # feedback from earlier audits lands with a delay; it lifts the weak criterion when received
        st["weak_level"] = min(4.6, st["weak_level"] + st["pending"])
        st["pending"] = 0.0
        scores = {}
        for cid, _, w, _ in RUBRIC:
            base = 4.1 + ag.skill + rng.normal(0, 0.55)
            if cid == ag.weak:
                base = st["weak_level"] + 0.5 * ag.skill + rng.normal(0, 0.6)
            scores[cid] = int(np.clip(np.round(base), 0, 5))
        if rng.random() < 0.035:
            scores["c6"] = int(rng.choice([0, 1]))          # identity not verified before an account change
        critical = scores["c6"] <= 1
        total = sum(scores[c] / 5 * w for c, _, w, _ in RUBRIC)
        if critical:
            total = min(total, 59)  # a security failure caps the audit
        band = next(b for t, b in BANDS if total >= t)
        audit_ts = day + pd.Timedelta(hours=int(rng.integers(9, 17)), minutes=int(rng.integers(60)))
        if automated:
            fb = audit_ts + pd.Timedelta(minutes=float(rng.uniform(1, 4)))
            ack = fb + pd.Timedelta(hours=float(rng.exponential(5)))
        else:
            # manual: feedback batched and emailed at the end of the week, some forgotten for a while
            fb = audit_ts + pd.Timedelta(days=float(rng.choice([3, 4, 5, 6, 7, 9, 12], p=[.15, .2, .2, .15, .15, .1, .05])))
            ack = fb + pd.Timedelta(hours=float(rng.exponential(30)))
        weak_failed = scores[ag.weak] <= 2
        # learning: specific feedback on the weak criterion helps more when it arrives quickly
        days_to_fb = (fb - audit_ts).total_seconds() / 86400
        if weak_failed:
            st["pending"] += 0.45 / (1 + days_to_fb / 1.0)
        flagged = [FLAG_TEXT[c] for c in scores if scores[c] <= 2]
        ch = rng.choice(CHANNEL[ag.team][0], p=CHANNEL[ag.team][1])
        rows.append(dict(audit_id=f"AUD{aid}", audit_ts=audit_ts, reviewer=rng.choice(REVIEWERS), agent_id=ag.agent_id,
                         channel=ch, interaction_ref=f"{ch[:2].upper()}-{rng.integers(100000, 999999)}",
                         **{f"{c}_score": scores[c] for c in scores}, critical_error=critical,
                         flagged_issues="; ".join(flagged), feedback_sent_at=fb, agent_acknowledged_at=ack,
                         process="Automated (Forms + Power Automate)" if automated else "Manual (spreadsheet + email)"))
        aid += 1

A = pd.DataFrame(rows)
for c in ("audit_ts", "feedback_sent_at", "agent_acknowledged_at"):
    A[c] = A[c].dt.strftime("%Y-%m-%d %H:%M")
A.to_csv(OUT / "audits.csv", index=False)
AG.drop(columns=["skill", "weak"]).to_csv(OUT / "agents.csv", index=False)
pd.DataFrame(RUBRIC, columns=["criterion_id", "criterion", "weight", "what_it_measures"]).to_csv(OUT / "rubric.csv", index=False)
pd.DataFrame([(lo, b) for lo, b in BANDS], columns=["min_score", "band"]).to_csv(OUT / "score_bands.csv", index=False)
print({"audits": len(A), "agents": len(AG)})
