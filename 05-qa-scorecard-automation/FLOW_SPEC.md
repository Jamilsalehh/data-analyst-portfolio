# Power Automate flows: exact steps

Two cloud flows, both built in **make.powerautomate.com** with a Microsoft 365 account (a work/school account or the free Microsoft 365 Developer sandbox).

The connectors used:
- Microsoft Forms
- Excel Online (Business)
- Office 365 Outlook
- Microsoft Teams

All of them are standard connectors, so no premium licence is needed.

Before you start, upload `templates/QA_Audit_Log_TEMPLATE.xlsx` to OneDrive. Rename it `QA_Audit_Log.xlsx`, delete the example row, and fill in the emails on the **Agents** sheet.

---

## The Microsoft Form: "QA Audit"

| # | Question | Type | Notes |
|---|---|---|---|
| 1 | Agent ID | Choice (drop-down) | QA001 … QA040, the same IDs as the Agents table |
| 2 | Channel | Choice | Call · Ticket · Chat |
| 3 | Interaction reference | Text | call ID / ticket number |
| 4 | Communication | Choice | 0 · 1 · 2 · 3 · 4 · 5 |
| 5 | Issue handling & SOP | Choice | 0–5 |
| 6 | Resolution & follow-up | Choice | 0–5 |
| 7 | Escalation & ownership | Choice | 0–5 |
| 8 | Accuracy & documentation | Choice | 0–5 |
| 9 | Security & compliance | Choice | 0–5 |
| 10 | Critical security error? (identity not verified before an account change) | Choice | Yes · No |
| 11 | Issues found | Long text | one line per issue |

Settings: **Only people in my organisation can respond**, and tick **Record name**. That makes the responder's email the `reviewer`.

Why Choice 0–5 instead of a Rating question: Forms ratings start at 1, and the rubric needs a 0 for "not done".

---

## Flow 1 · "QA audit → log → score → feedback" (Automated cloud flow)

| # | Action | Settings |
|---|---|---|
| 1 | **When a new response is submitted** (Forms) | Form: QA Audit |
| 2 | **Get response details** (Forms) | Response Id: *List of response notifications Response Id*. Power Automate wraps the next steps in *Apply to each*, which is fine. |
| 3 | **Compose**, rename it `AuditId` | `concat('AUD-', formatDateTime(utcNow(), 'yyyyMMddHHmmssfff'))` |
| 4 | **Compose**, rename it `NowBeirut` | `convertTimeZone(utcNow(), 'UTC', 'Middle East Standard Time', 'yyyy-MM-dd HH:mm')` |
| 5 | **Get a row** (Excel Online Business), rename it `Get_agent` | File: QA_Audit_Log.xlsx · Table: **Agents** · Key column: `agent_id` · Key value: *Agent ID* answer |
| 6 | **Add a row into a table**, rename it `Add_audit` | Table: **Audits**. Map the columns as listed below this table. |
| 7 | **Delay** | 5 seconds. This gives Excel time to calculate the formula columns. |
| 8 | **Get a row**, rename it `Get_audit` | Table: **Audits** · Key column: `audit_id` · Key value: `outputs('AuditId')` |
| 9 | **Condition**, rename it `Needs_coaching` | Expression: `or(less(float(outputs('Get_audit')?['body/score']), 70), equals(toLower(string(outputs('Get_audit')?['body/critical_error'])), 'true'))` |
| 10 | **If yes →** | the four actions listed below this table |
| 11 | **If no →** | **Send an email (V2)** to the agent. Subject: `QA audit: @{outputs('Get_audit')?['body/band']} (@{outputs('Get_audit')?['body/score']})`. Short thank-you body. |

**Step 6, column mapping for Add a row into a table:**

| Column | Value |
|---|---|
| audit_id | `outputs('AuditId')` |
| audit_ts | `outputs('NowBeirut')` |
| reviewer | *Responders' Email* |
| agent_id | the answer |
| agent_name | `Get_agent` → `agent_name` |
| team | `Get_agent` → `team` |
| channel, interaction_ref | the answers |
| c1_score … c6_score | the six 0–5 answers |
| critical_error | `if(equals(<Critical answer>, 'Yes'), 'TRUE', 'FALSE')` |
| flagged_issues | the answer |
| feedback_sent_at | `outputs('NowBeirut')` |
| process | `Automated (Forms + Power Automate)` |

Leave `score`, `band` and `hours_to_feedback` empty. They are formula columns in the table and fill themselves.

**Step 10, the "If yes" branch:**
1. **Send an email (V2)** to the team lead (`Get_agent` → `lead_email`). Subject: `Coaching needed: @{outputs('Get_agent')?['body/agent_name']} scored @{outputs('Get_audit')?['body/score']}`. The body holds the HTML template below.
2. **Send email with options** (Outlook) to the agent (`Get_agent` → `agent_email`).
   - User options: `Acknowledge,I'd like to discuss`
   - Subject: `QA audit @{outputs('AuditId')}: @{outputs('Get_audit')?['body/band']}`
   - Body: the same template.
   - This action waits for the agent to click a button.
3. **Update a row** on table Audits, key `audit_id`. Set `agent_acknowledged_at` = `convertTimeZone(utcNow(), 'UTC', 'Middle East Standard Time', 'yyyy-MM-dd HH:mm')`.
4. **Condition:** `SelectedOption` is equal to `I'd like to discuss`. If yes, add **Post message in a chat or channel** (Teams) to the reviewer: "@agent wants to discuss audit AuditId".

**Email body template** (HTML in the email action):
```html
<p>Hi @{outputs('Get_agent')?['body/agent_name']},</p>
<p>Your @{outputs('Get_audit')?['body/channel']} <b>@{outputs('Get_audit')?['body/interaction_ref']}</b> was reviewed today.</p>
<table border="1" cellpadding="4" style="border-collapse:collapse">
  <tr><th align="left">Criterion</th><th>Score (0–5)</th></tr>
  <tr><td>Communication</td><td>@{outputs('Get_audit')?['body/c1_score']}</td></tr>
  <tr><td>Issue handling &amp; SOP</td><td>@{outputs('Get_audit')?['body/c2_score']}</td></tr>
  <tr><td>Resolution &amp; follow-up</td><td>@{outputs('Get_audit')?['body/c3_score']}</td></tr>
  <tr><td>Escalation &amp; ownership</td><td>@{outputs('Get_audit')?['body/c4_score']}</td></tr>
  <tr><td>Accuracy &amp; documentation</td><td>@{outputs('Get_audit')?['body/c5_score']}</td></tr>
  <tr><td>Security &amp; compliance</td><td>@{outputs('Get_audit')?['body/c6_score']}</td></tr>
</table>
<p><b>Total: @{outputs('Get_audit')?['body/score']} / 100 · @{outputs('Get_audit')?['body/band']}</b></p>
<p>What to work on: @{outputs('Get_audit')?['body/flagged_issues']}</p>
```

**Error handling:** add a parallel branch after `Add_audit` and set it to **Configure run after → has failed**. In it, send an email to the QA mailbox with `workflow()?['run']?['name']`, so a failed audit is never lost silently.

---

## Flow 2 · "Weekly QA summary" (Scheduled cloud flow)

| # | Action | Settings |
|---|---|---|
| 1 | **Recurrence** | Every 1 week · Monday · 08:00 · Time zone (UTC+02:00/+03:00) Beirut |
| 2 | **List rows present in a table** | Table: Audits · *Show advanced options* → **DateTime Format: ISO 8601**. Without this, dates come back as Excel serial numbers. |
| 3 | **Filter array**, rename it `Last7Days` | From: `value` · `@greaterOrEquals(item()?['audit_ts'], addDays(utcNow(), -7))` |
| 4 | **Filter array**, rename it `Below70` | From: `body('Last7Days')` · `@less(float(item()?['score']), 70)` |
| 5 | **Select** | From: `body('Below70')` · Map: Agent → `item()?['agent_name']`, Score → `item()?['score']`, Band → `item()?['band']`, Issues → `item()?['flagged_issues']` |
| 6 | **Create HTML table** | From: the Select output |
| 7 | **Send an email (V2)** to the QA manager | Subject: `QA weekly: @{length(body('Last7Days'))} audits, @{length(body('Below70'))} under 70`. Body: a short intro, then the HTML table. |

**Large tables:** List rows returns 256 rows by default. Under **Settings → Pagination**, turn it on and set the threshold to 5000.

---

## Optional: Power Apps instead of Forms

If reviewers want to see the agent's last scores while auditing, build a **canvas app** on the same Excel tables, or move them to a SharePoint list for better performance.
- **Screen 1:** agent gallery showing each agent's average score.
- **Screen 2:** an audit form with six sliders (0–5), a critical-error toggle and a notes box, plus a live total computed with `Slider1.Value/5*15 + …`.
- **Submit:** `Patch(Audits, Defaults(Audits), {...})`. The same Flow 1 then picks the new row up with the trigger *When a row is added* (SharePoint), or the app calls the flow directly with `PowerAutomate.Run`.
