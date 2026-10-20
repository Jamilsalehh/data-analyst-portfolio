# Build guide: Agent-Network Collections Pipeline

Time needed: 4–6 hours. You already build this kind of pipeline at work, so most of this will feel familiar. The goal here is a clean, shareable copy you can walk through in an interview.

---

## Part 1: Set up the Google Sheet

1. Create a new Google Sheet named **Collections Pipeline (portfolio)**.
2. **File → Settings:**
   - Locale **Lebanon** (or United Kingdom)
   - Time zone **(GMT+03:00) Beirut**
   - Save
3. Create two seed tabs and fill them from `data/seed/`:
   - `CONFIG`: paste `CONFIG.csv`, with columns key and value
   - `DIM_INSURER`: paste `DIM_INSURER.csv`, with columns alias and insurer
4. Import the July files. Use **File → Import → Upload → `payments_2026-07.csv`**, with these settings:
   - Import location: **Insert new sheet(s)**, then rename the tab to `RAW_PAYMENTS`
   - **Convert text to numbers, dates, and formulas: NO** (untick it). This matters. If it's on, Sheets may read `01/07/2026` as 7 January.
5. Do the same for `policy_sales_2026-07.csv` and rename that tab `RAW_POLICY_SALES`.

## Part 2: Add the script

1. **Extensions → Apps Script.** Delete the sample code and paste all of `apps_script/Code.gs`. Save.
2. In the Apps Script editor go to **Project Settings** and set the time zone to Beirut.
3. Reload the spreadsheet. A **Pipeline** menu appears.
4. **Pipeline → Load raw sheets.** The first run asks for permission. Approve it: the script is yours and it only touches this sheet.
5. Check that the run created the output tabs `FCT_PAYMENTS`, `FCT_POLICY_SALES`, `MART_DAILY`, `DIM_AGENT`, `DQ_LOG` and `LOAD_LOG`.
6. For August and September, import each month's files with **Replace current sheet** on the RAW tabs, then run the load again.
7. **Prove it's idempotent:** re-import September and load it again. `FCT_PAYMENTS` should stay at 30,659 rows, and `LOAD_LOG` should show `days_replaced = 30`.

Your numbers should match `tests/output/LOAD_LOG.csv`:

| Month | Raw rows | Duplicates skipped | Loaded | Flagged |
|---|---|---|---|---|
| Jul | 10,501 | 41 | 10,460 | 277 |
| Aug | 10,346 | 47 | 10,299 | 251 |
| Sep | 9,952 | 52 | 9,900 | 255 |

Optional: add a time-driven trigger (Triggers → Add trigger → `runLoad`, daily) to show you know how scheduling works.

## Part 3: Looker Studio report

Use your real "Mechanic payments" report as the visual template. The structure below follows it.

**Data sources:** `FCT_PAYMENTS`, `MART_DAILY`, `DIM_AGENT` (Google Sheets connector).

**Calculated fields on `FCT_PAYMENTS`:**

| Field | Formula |
|---|---|
| Payments | `COUNT(txn_key)` |
| Collected USD | `SUM(amount_usd)` |
| Avg Payment | `AVG(amount_usd)` |
| Active Agents | `COUNT_DISTINCT(agent_code)` |
| Same-day Policy % | `SUM(CASE WHEN bought_here_same_day = true THEN 1 ELSE 0 END) / COUNT(txn_key)` |
| Passed Checks % | `SUM(CASE WHEN dq_status = "ok" THEN 1 ELSE 0 END) / COUNT(txn_key)` |
| Late-month | `CASE WHEN DAY(txn_date) >= 24 THEN "24th–month end" ELSE "1st–23rd" END` |

If Sheets stores `bought_here_same_day` as text, use `= "TRUE"` instead of `= true`.

**Page layout:** a single long page with section headers, like your real report.
1. **Header:** title, subtitle "Vehicle fee payments collected through Northwind agents · USD", and filters for Agent network, Insurer and Date range.
2. **Scorecards:** Collected USD, Payments, Avg Payment, Active Agents, Payments per day (`COUNT(txn_key)/COUNT_DISTINCT(txn_date)`), Same-day Policy %.
3. **Collections over time:** area chart of Collected USD by txn_date. Add a reference band or note for the 24th–month-end rush.
4. **Agent networks and top agents:**
   - Table by agent_network: Active Agents, Collected USD, Avg Payment, share of total (*Percent of total* in the metric settings).
   - Top 10 agents table from `DIM_AGENT`.
   - Scorecard "Collections from the top 50 agents" (filter tier_last_30d = Top 50, or calculate it in the table).
5. **Insurers and cross-sell:**
   - Bar chart of Same-day Policy % by agent_network.
   - Table by insurer: Payments, Same-day Policy %.
   - Time series of weekly policies sold from `MART_DAILY` (`SUM(policies_sold)`).
6. **Timing:**
   - Heatmap pivot of weekday × txn_hour by Payments.
   - Bar chart of insurance_timing (Same day / Before / After / Unknown).
7. **Data health:**
   - Scorecard Passed Checks %.
   - Table of dq_flags by count of payments, filtered to `dq_status = "review"`.
   - Text box linking to the `DQ_LOG` tab ("View flagged payments →").

Share the Sheet and the report as **Anyone with the link → Viewer**. The data is synthetic, so this is safe.

## Part 4: GitHub
Add screenshots of the dashboard and of the `LOAD_LOG` tab to `images/`. Recruiters like seeing the pipeline's own audit trail. Then push.
