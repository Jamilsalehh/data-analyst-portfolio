-- =====================================================================
-- 05_rfm_segments.sql  ·  Who to talk to now (as of 30 Sep 2026)
-- Recency, Frequency, Monetary scored 1-5 with NTILE over users who
-- transacted in the last 6 months, then mapped to plain-English segments.
-- =====================================================================

CREATE OR REPLACE TABLE wallet.rfm AS
WITH base AS (
  SELECT
    user_id,
    DATE_DIFF(DATE '2026-09-30', DATE(MAX(CAST(txn_ts AS TIMESTAMP))), DAY)   AS recency_days,
    COUNT(*)                                                                AS frequency,
    SUM(revenue_usd)                                                        AS monetary_usd
  FROM wallet.transactions
  WHERE status = 'completed'
    AND DATE(CAST(txn_ts AS TIMESTAMP)) >= DATE '2026-04-01'
  GROUP BY user_id
),
scored AS (
  SELECT
    *,
    6 - NTILE(5) OVER (ORDER BY recency_days)   AS r_score,   -- most recent = 5
    NTILE(5) OVER (ORDER BY frequency)          AS f_score,
    NTILE(5) OVER (ORDER BY monetary_usd)       AS m_score
  FROM base
)
SELECT
  *,
  CASE
    WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN '1 Champions'
    WHEN r_score >= 3 AND f_score >= 3                  THEN '2 Loyal'
    WHEN r_score >= 4 AND f_score <= 2                  THEN '3 New / promising'
    WHEN r_score <= 2 AND f_score >= 3                  THEN '4 At risk (were active)'
    WHEN r_score <= 2 AND f_score <= 2                  THEN '5 Slipping away'
    ELSE '6 Needs attention'
  END AS segment
FROM scored;


SELECT
  segment,
  COUNT(*)                                                      AS users,
  ROUND(COUNT(*) * 100 / SUM(COUNT(*)) OVER (), 1)               AS share_of_users_pct,
  ROUND(SUM(monetary_usd) * 100 / SUM(SUM(monetary_usd)) OVER (), 1) AS share_of_revenue_pct,
  ROUND(AVG(recency_days), 0)                                    AS avg_days_since_last_txn
FROM wallet.rfm
GROUP BY segment
ORDER BY segment;
