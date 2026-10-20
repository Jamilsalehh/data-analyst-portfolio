# Build guide: QA Scorecard Automation

Time needed: about 6 hours.

**What you need:** a Microsoft 365 account with Forms, Power Automate and OneDrive. If you don't have a personal one, join the free **Microsoft 365 Developer Program**. It gives you a sandbox tenant with every app this project uses. Power BI Desktop is free.

---

## Part 1: The audit log (30 min)
1. Open `templates/QA_Audit_Log_TEMPLATE.xlsx` in Excel. Read the **How to use** tab, then look at the formulas in the blue columns of **Audits**:
   - `score`: weighted sum, with a cap at 59 for a critical error
   - `band`: `LOOKUP` into the Bands sheet
   - `hours_to_feedback`
2. Change one weight on **Rubric**, e.g. Communication from 15 to 20, and watch the example row's score change. Then put it back. Be ready to explain this in an interview: "the weights live in one place".
3. Fill in `agent_email` and `lead_email` on **Agents**. Use your own address for every row while testing.
4. Delete the example row and upload the file to OneDrive as `QA_Audit_Log.xlsx`.

## Part 2: Form + flows (3 hours)
Follow [`FLOW_SPEC.md`](FLOW_SPEC.md) step by step.

**Test cases.** Submit these through the Form and check what happens:

| Test | Scores c1–c6 | Critical? | Expected |
|---|---|---|---|
| Strong audit | 5,5,4,5,4,5 | No | score 94, Outstanding. The agent gets a thank-you email. |
| Weak audit | 3,2,3,3,3,4 | No | score 58, Critical. The lead gets an email, the agent gets one with buttons. |
| Security fail | 5,5,5,5,5,0 | Yes | score capped at 59, Critical, even though the other criteria are perfect. |

Click **Acknowledge** in the agent email and confirm that `agent_acknowledged_at` fills in. Then run Flow 2 manually (**Test → Manually**) and check the weekly email.

Take screenshots of:
- both flows in the designer (expanded)
- one feedback email
- the Excel log with rows added by the flow

These go in `images/`, and they are the proof that you built it.

## Part 3: Power BI report on the log (2 hours)

Use `data/QA_Audit_Log_SAMPLE.xlsx`, which holds 6 months of audits, so the charts have history. Later you can point the same report at the live OneDrive file.

**Power Query**
1. Get data → Excel workbook → tick the **Audits**, **Agents** and **Rubric** tables. Use the tables, not the sheets.
2. Duplicate *Audits* and rename the copy `CriteriaScores`.
   - Keep `audit_id` and `c1_score`…`c6_score`.
   - Select the six score columns → **Unpivot columns**.
   - Rename the columns to `criterion_col` and `points`.
   - Add a column `criterion_id = Text.Start([criterion_col], 2)`.
   - Merge with **Rubric** on `criterion_id` and expand `criterion` and `weight`.
3. Make sure `audit_ts`, `feedback_sent_at` and `agent_acknowledged_at` are typed **Date/Time**.

**Model**
- Relationships: `Audits[agent_id]` → `Agents[agent_id]` and `CriteriaScores[audit_id]` → `Audits[audit_id]`.
- Add a date table, as in project 2, related on the date of `audit_ts`. Create the column `audit_date = DATEVALUE(Audits[audit_ts])`.

**Measures**
```dax
Audits Count = COUNTROWS ( Audits )
Avg Score = AVERAGE ( Audits[score] )
% Below 70 = DIVIDE ( CALCULATE ( [Audits Count], Audits[score] < 70 ), [Audits Count] )
Critical Errors = CALCULATE ( [Audits Count], Audits[critical_error] = TRUE () )
Median Minutes to Feedback =
    MEDIANX ( Audits, DATEDIFF ( Audits[audit_ts], Audits[feedback_sent_at], MINUTE ) )
Median Hours to Acknowledge =
    MEDIANX ( FILTER ( Audits, NOT ISBLANK ( Audits[agent_acknowledged_at] ) ),
              DATEDIFF ( Audits[feedback_sent_at], Audits[agent_acknowledged_at], MINUTE ) / 60 )
Avg Points (0-5) = AVERAGE ( CriteriaScores[points] )
Fail Count (≤2) = CALCULATE ( COUNTROWS ( CriteriaScores ), CriteriaScores[points] <= 2 )
```

**Pages**
1. **QA Overview**
   - Cards: Audits Count, Avg Score, % Below 70, Critical Errors, Median Minutes to Feedback.
   - Column chart of Audits Count by `band`, colours red → green.
   - Line chart of Avg Score by month.
2. **Agent Scorecard**
   - Slicer on agent.
   - Cards for that agent.
   - Line chart of their score by audit date, with a constant line at 70.
   - Table of their last 10 audits, including flagged_issues.
3. **Criteria Heatmap**
   - Matrix: rows = agent_name, columns = criterion, values = Avg Points (0–5).
   - Conditional formatting background colour scale, red (0) to green (5).
   - This shows each agent's weak spot at a glance.
4. **Before / After Automation**
   - Clustered columns by `process`: Median Minutes to Feedback, % Below 70, Avg Score.
   - A text box with the repeat-mistake result from the README (48% → 9%). That number comes from the analysis script.

**Check:** with no filters, Audits Count = 1,572, Avg Score ≈ 78.1, Critical Errors = 66, and Median Minutes to Feedback for the automated process = 2.
