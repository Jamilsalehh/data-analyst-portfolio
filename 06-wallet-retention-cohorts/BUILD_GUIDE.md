# Build guide: Wallet Retention & Cohorts

Time needed: 5–7 hours. This project shows you can go **from SQL to a business recommendation**. Know every query well enough to rewrite it on a whiteboard.

---

## Part 1: BigQuery
1. In your sandbox project, create the dataset `wallet`.
2. Unzip `data/transactions.csv.zip` first (zipped to stay under GitHub's upload size). Then upload `users.csv`, `transactions.csv` and `marketing_spend.csv` with auto-detect. Name each table after its file.
   - `transactions.csv` is 14 MB. Upload works up to 100 MB.
   - On `marketing_spend`, check that `month` came in as STRING (values like "2026-01"). If auto-detect made it a DATE, edit the schema.
3. Run the files in order. `01` and `05` *create tables* (`user_month`, `user_summary`, `rfm`) that the later files read.
4. Your results should match these values:

| Check | Value |
|---|---|
| users / transacted / activated | 10,515 / 9,668 / 3,537 |
| Oct 2025 cohort M3 retention | 49.9% |
| M3 retention, Referral / Social ads | 66.1% / 23.0% |
| M3 activated vs not | 73.3% vs 40.9% |
| Social ads CAC / 6-month revenue per user | $11.17 / $4.67 |
| Champions share of revenue | 43.9% |

## Part 2: Power BI
**Get data → Google BigQuery.** Sign in with the same Google account and import `user_summary`, `user_month`, `rfm` and `marketing_spend`. If the connector gives you trouble, run each table in BigQuery, use **Save results → CSV**, and load the CSVs instead.

**Model:** `user_month[user_id]` → `user_summary[user_id]` (many-to-one). `rfm[user_id]` → `user_summary[user_id]` (one-to-one, single direction).

**Measures**
```dax
Users = COUNTROWS ( user_summary )
Active Users = DISTINCTCOUNT ( user_month[user_id] )
Retention % = DIVIDE ( [Active Users], [Users] )
Activated % = DIVIDE ( CALCULATE ( [Users], user_summary[activated_14d] = TRUE () ), [Users] )
Revenue = SUM ( user_summary[revenue_usd] )
Revenue per User = DIVIDE ( [Revenue], [Users] )
Churned % = DIVIDE ( CALCULATE ( [Users], user_summary[churned_60d] = TRUE () ), [Users] )
M3 Retention % =
VAR eligible = CALCULATETABLE ( VALUES ( user_summary[user_id] ), user_summary[cohort_month] <= DATE ( 2026, 6, 1 ) )
VAR retained = CALCULATE ( DISTINCTCOUNT ( user_month[user_id] ), user_month[month_number] = 3, eligible )
RETURN DIVIDE ( retained, COUNTROWS ( eligible ) )
```

**Pages**
1. **Cohort heatmap.** Matrix with rows = `user_summary[cohort_month]` (formatted "mmm yy") and columns = `user_month[month_number]`. Value: **Retention %**.
   - Conditional formatting → background colour scale, white to dark blue.
   - Cells are only filled where data exists, so the triangle shape appears by itself.
   - This works because the month_number column filters only `user_month`, while the row filters `user_summary`. Make sure you can explain why. It's a classic interview question.
2. **Channels.**
   - Clustered bar of M3 Retention % by acquisition_channel, with Activated as the legend. You'll need a column `Activated = IF(user_summary[activated_14d], "Paid a bill in 14 days", "Didn't")`.
   - Table: channel, Users, Activated %, M3 Retention %, Revenue per User.
3. **Payback.** Add a table built in Power Query from `04_payback_by_channel.sql` (run it, save as CSV, import), or rebuild it in DAX using `marketing_spend`. Show a clustered column of CAC vs 6-month revenue per user by channel.
4. **RFM segments.** A treemap of users by segment, a bar of revenue share by segment, and a table of the "At risk" users (user_id, recency_days, frequency, monetary_usd) as the export list for the CRM team.

## Part 3: Publish
Take screenshots of each page into `images/`, upload the `.pbix`, and add a 2-minute video walkthrough. Lead with the recommendation, then show the cohort heatmap as the proof.
