-- =====================================================================
-- 01_base_tables.sql  ·  BigQuery Standard SQL  ·  dataset: wallet
-- Builds the two tables every other query uses:
--   user_summary : one row per user (cohort, channel, activation, first/last activity, revenue)
--   user_month   : one row per user per month they made a completed transaction
-- =====================================================================

CREATE OR REPLACE TABLE wallet.user_month AS
SELECT DISTINCT
  t.user_id,
  DATE_TRUNC(DATE(CAST(u.signup_ts AS TIMESTAMP)), MONTH)                     AS cohort_month,
  DATE_TRUNC(DATE(CAST(t.txn_ts AS TIMESTAMP)), MONTH)                        AS activity_month,
  DATE_DIFF(DATE_TRUNC(DATE(CAST(t.txn_ts AS TIMESTAMP)), MONTH),
            DATE_TRUNC(DATE(CAST(u.signup_ts AS TIMESTAMP)), MONTH), MONTH)  AS month_number
FROM wallet.transactions AS t
JOIN wallet.users AS u USING (user_id)
WHERE t.status = 'completed';


CREATE OR REPLACE TABLE wallet.user_summary AS
WITH first14 AS (
  -- "activated" = paid a bill or a merchant within 14 days of signing up
  SELECT
    u.user_id,
    LOGICAL_OR(t.txn_type IN ('Bill payment', 'Merchant payment')
               AND t.status = 'completed'
               AND CAST(t.txn_ts AS TIMESTAMP) < TIMESTAMP_ADD(CAST(u.signup_ts AS TIMESTAMP), INTERVAL 14 DAY)) AS activated_14d
  FROM wallet.users AS u
  LEFT JOIN wallet.transactions AS t USING (user_id)
  GROUP BY u.user_id
),
activity AS (
  SELECT
    user_id,
    COUNT(*)                                       AS completed_txns,
    MIN(CAST(txn_ts AS TIMESTAMP))                 AS first_txn_ts,
    MAX(CAST(txn_ts AS TIMESTAMP))                 AS last_txn_ts,
    SUM(revenue_usd)                               AS revenue_usd,
    SUM(amount_usd)                                AS volume_usd
  FROM wallet.transactions
  WHERE status = 'completed'
  GROUP BY user_id
)
SELECT
  u.user_id,
  DATE_TRUNC(DATE(CAST(u.signup_ts AS TIMESTAMP)), MONTH)          AS cohort_month,
  u.acquisition_channel,
  u.region,
  u.age_band,
  u.kyc_level,
  COALESCE(f.activated_14d, FALSE)                                 AS activated_14d,
  a.first_txn_ts IS NOT NULL                                       AS ever_transacted,
  COALESCE(a.completed_txns, 0)                                    AS completed_txns,
  a.first_txn_ts,
  a.last_txn_ts,
  COALESCE(a.revenue_usd, 0)                                       AS revenue_usd,
  COALESCE(a.volume_usd, 0)                                        AS volume_usd,
  -- churned = no completed transaction in the 60 days before the data cut-off (30 Sep 2026)
  a.last_txn_ts IS NULL OR a.last_txn_ts < TIMESTAMP '2026-08-01 23:59:59' AS churned_60d
FROM wallet.users AS u
LEFT JOIN first14 AS f USING (user_id)
LEFT JOIN activity AS a USING (user_id);


-- sanity checks
SELECT
  (SELECT COUNT(*) FROM wallet.users)                                  AS users,
  (SELECT COUNTIF(ever_transacted) FROM wallet.user_summary)           AS users_who_transacted,
  (SELECT COUNTIF(activated_14d) FROM wallet.user_summary)             AS activated_users,
  (SELECT COUNT(*) FROM wallet.user_month)                             AS user_month_rows;
