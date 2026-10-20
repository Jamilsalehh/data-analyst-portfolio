# Build guide: Contact Center Performance

Time needed: about 4–6 hours over two evenings. You build everything yourself, so you can explain every chart in an interview.

---

## Part 1: Load the data into BigQuery (free sandbox, no card needed)

1. Go to **console.cloud.google.com/bigquery** with your personal Gmail and accept the sandbox terms. Create a project, e.g. `jamil-portfolio`.
2. In the Explorer panel, click the three dots next to your project → **Create dataset** → ID `contact_center` → location `EU` → Create.
3. For each CSV in `data/`, click the dataset's three dots → **Create table**:
   - Source: **Upload** → choose the file → File format **CSV**
   - Table name: the file name without `.csv` (`agents`, `calls_queue_hourly`, `calls_agent_daily`, `tickets`)
   - Schema: tick **Auto detect** → Create table
4. Open a new query tab, paste all of `sql/01_clean_views.sql` and click **Run**. You now have two views: `v_agent_daily` and `v_tickets`. The last query prints the data-quality summary. You should see 68 duplicates, 154 unmapped rows, 1,739 status fixes and 40 bad timestamps.
5. Run the queries in `02_…`, `03_…` and `04_…` one at a time. Highlight a query and press Ctrl+Enter to run just that one. Check that your numbers match the README.

> Sandbox tables expire after 60 days. That's fine while you build. To keep the public dashboard alive longer, do one of two things. Either turn on billing (this project stays far inside the free tier, so the cost is $0) and remove the expiry in each table's details. Or save each view's results to Google Sheets (**Save results → Google Sheets**) and point Looker Studio at the sheets instead.

## Part 2: Connect Looker Studio

1. Go to **lookerstudio.google.com** → **Blank report** → **BigQuery** → your project → `contact_center`.
2. Add these four sources: `calls_queue_hourly`, `v_agent_daily`, `v_tickets` and `agents`. Use **Add data** for each one after the first.
3. Theme: **Theme and layout** → pick a simple light theme. Use one accent color for "good" and one for "bad", and keep them the same everywhere.

### Calculated fields

To add each one: Resource → Manage added data sources → Edit → **Add a field**.

**On `calls_queue_hourly`:**

| Field name | Formula | Type |
|---|---|---|
| Answer Rate | `SUM(answered) / SUM(offered)` | Percent |
| Abandon Rate | `SUM(abandoned) / SUM(offered)` | Percent |
| Service Level 20s | `SUM(answered_within_20s) / SUM(offered)` | Percent |
| ASA (s) | `SUM(total_answer_delay_s) / SUM(answered)` | Number |
| Hour label | `CONCAT(CAST(call_hour AS TEXT), ":00")` | Text |

**On `v_agent_daily`:**

| Field name | Formula | Type |
|---|---|---|
| Active Agents | `COUNT_DISTINCT(agent_id)` | Number |
| Pickup Rate | `SUM(answered) / SUM(presented)` | Percent |
| Calls per Logged Hour | `SUM(answered) / (SUM(logged_in_s) / 3600)` | Number |
| Occupancy | `SUM(talk_s) / (SUM(logged_in_s) - SUM(break_s) - SUM(not_ready_s))` | Percent |

**On `v_tickets`:**

| Field name | Formula | Type |
|---|---|---|
| Tickets | `COUNT(ticket_id)` | Number |
| Solved Tickets | `SUM(CASE WHEN status IN ("Solved", "Closed") THEN 1 ELSE 0 END)` | Number |
| Open Backlog | `SUM(CASE WHEN status IN ("Open", "Pending", "New") THEN 1 ELSE 0 END)` | Number |
| Median First Reply (min) | `MEDIAN(first_reply_min)` | Number |
| CSAT | `SUM(CASE WHEN satisfaction = "good" THEN 1 ELSE 0 END) / SUM(CASE WHEN satisfaction IN ("good", "bad") THEN 1 ELSE 0 END)` | Percent |
| First Reply Bucket | `CASE WHEN first_reply_min <= 60 THEN "1) < 1h" WHEN first_reply_min <= 120 THEN "2) 1-2h" WHEN first_reply_min <= 240 THEN "3) 2-4h" WHEN first_reply_min <= 480 THEN "4) 4-8h" ELSE "5) > 8h" END` | Text |
| Replied Within 4h | `SUM(CASE WHEN first_reply_min <= 240 THEN 1 ELSE 0 END) / COUNT(first_reply_min)` | Percent |

## Part 3: Build the four pages

Your real Calls & Tickets report already uses this layout, so keep the same look.

### Page 1: Calls Overview (source: `calls_queue_hourly`)
- **Controls (top right):** Date range control and a drop-down on `queue`.
- **Scorecards (one row):** Offered (SUM), Answered, Abandoned, Answer Rate, Abandon Rate, ASA (s). Turn on **comparison to previous period** so each card shows a ▲/▼.
- **Time series:** dimension `call_date`; metrics offered, answered, abandoned. Under Style, make abandoned red.
- **Table, "Queue performance":** dimension `queue`; metrics offered, answered, abandoned, Answer Rate, Abandon Rate, Service Level 20s, ASA (s). Add heatmap shading on Answer Rate.
- **Pivot table, "When callers give up":**
  - Row dimension: `call_date`. In the dimension's settings, change its type to **Day of week**.
  - Column dimension: Hour label.
  - Metric: Abandon Rate.
  - Style → **Heatmap**.
  - Filter: queue = App Support.
  - This is the lunchtime chart from the README.

### Page 2: Agent Performance (source: `v_agent_daily`)
- **Controls:** Date range, drop-downs on `team` and `agent_name`.
- **Scorecards:** Presented, Active Agents, Answered, Pickup Rate.
- **Table, "Agent ranking":** agent_name, team, presented, answered, Pickup Rate, Calls per Logged Hour, Occupancy. Sort by answered (descending). Use bar-style cells for answered.
- **Bar chart, "Top 10 agents by answered calls":** set the row limit to 10.
- **Time series, "Agents on the phones per day":** dimension work_date, metric Active Agents, filter queue = App Support. Put it next to a second time series of Answer Rate from page 1. This is the staffing story.
- **Filter on this page:** exclude `is_unmapped = true` from rankings. Add a small note saying unmapped temp IDs are excluded.

### Page 3: Tickets Overview (source: `v_tickets`)
- **Scorecards:** Tickets, Solved Tickets, Median First Reply (min), CSAT, Open Backlog.
- **Time series:** created_date by Tickets and Solved Tickets.
- **Time series:** created_date by Median First Reply (min). The August spike should be obvious.
- **Table, "Team performance":** entity, Tickets, Median First Reply (min), CSAT, plus median resolution: add `MEDIAN(resolution_h)` as a field.
- **Bar chart:** First Reply Bucket by CSAT. Sort by the bucket name ascending, which is why the labels start with 1), 2)…
- **Donut:** status by Tickets.

### Page 4: Insights
Three text boxes, each with one chart next to it. Copy the three findings from the README, in your own words.

## Part 4: Finish and publish

1. **Share** → Manage access → "Anyone with the link can **view**". This is safe because the data is synthetic.
2. Take one clean screenshot per page. Use **View** mode and hide the left page list. Save them as `images/page1.png` … `page4.png`.
3. In the README, add the public dashboard link under the title.
4. Push the folder to GitHub (see the portfolio README for the steps).

## Checks before you call it done

- Scorecard totals match the SQL. For example, App Support answer rate in August is 78.5%.
- Every chart has a title that says what it shows, not just "Chart 1".
- Nothing is left unformatted: percentages show as %, seconds show "s".
- The date range control changes every chart on the page.
