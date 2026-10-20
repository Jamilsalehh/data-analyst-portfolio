# Build guide: Card Top-up Investigation

Time needed: 2–3 hours. This project is mainly about SQL, so the work is to run the queries yourself, understand each one, and be able to rewrite any of them from memory.

## 1. Load the data
1. In BigQuery (the same sandbox project as project 1), create the dataset `topups`.
2. Upload `data/topup_attempts.csv` → table `topup_attempts`, and `data/accounts.csv` → table `accounts`. Use CSV with schema auto-detect.

## 2. Run the files in order
| File | What to check |
|---|---|
| `01_clean.sql` | raw_rows 30,731 → clean_rows 30,611. 911 rows with missing currency |
| `02_find_the_problem.sql` | Issuer 03: 85.0% → 0.3%. The last accepted attempt is 25 Aug 08:43 |
| `03_rule_out_causes.sql` | 0 accepted on every gateway for Issuer 03. Other issuers: 81.6–82.7% |
| `04_customer_impact.sql` | 831 customers, 3,888 attempts, 7.4% saved by another card, $231K intended |

## 3. Practise explaining it (this is the interview)
For each query, say out loud in one sentence:
1. **what question** it answers
2. **why** that SQL feature is used, e.g. "`QUALIFY` lets me filter on a window function without a subquery"
3. **what the result means** for the business

SQL features in this project worth knowing cold:
- `QUALIFY ROW_NUMBER() OVER (PARTITION BY … ORDER BY …) = 1`: deduplication
- `COUNTIF(...)` and `SAFE_DIVIDE` for rates in one pass
- `SUM(COUNT(*)) OVER (PARTITION BY gateway)`: share within a group
- `LOGICAL_OR(...)` inside a `GROUP BY`: "did any later attempt succeed?"
- the self-join in `04` #2: the same table joined on account and later time
- `STRING_AGG(DISTINCT …)`: list the reasons seen per gateway

## 4. Optional: a one-page Looker Studio view
Connect `v_attempts` and build three charts:
- a time series of acceptance rate (`SUM(CASE WHEN accepted THEN 1 ELSE 0 END)/COUNT(attempt_id)`), broken down by issuer
- a bar chart of failure_reason by gateway, filtered to Issuer 03
- a scorecard row: customers affected, failed attempts, intended USD

Screenshot it into `images/`.
