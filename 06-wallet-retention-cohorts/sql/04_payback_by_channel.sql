-- =====================================================================
-- 04_payback_by_channel.sql  ·  Do paid channels earn back what they cost?
-- CAC = spend / signups.  Revenue per user = fee revenue in the user's first
-- 6 months (cohorts up to Mar 2026, so every user has 6 full months).
-- =====================================================================

WITH spend AS (
  SELECT channel, SUM(spend_usd) AS spend_usd
  FROM wallet.marketing_spend
  WHERE month <= '2026-03'
  GROUP BY channel
),
users_6m AS (
  SELECT user_id, acquisition_channel, cohort_month
  FROM wallet.user_summary
  WHERE cohort_month <= '2026-03-01'
),
rev_6m AS (
  SELECT
    u.acquisition_channel,
    SUM(t.revenue_usd) AS revenue_6m_usd
  FROM users_6m AS u
  JOIN wallet.transactions AS t USING (user_id)
  WHERE t.status = 'completed'
    AND DATE(CAST(t.txn_ts AS TIMESTAMP)) < DATE_ADD(u.cohort_month, INTERVAL 6 MONTH)
  GROUP BY u.acquisition_channel
),
counts AS (
  SELECT acquisition_channel, COUNT(*) AS signups
  FROM users_6m
  GROUP BY acquisition_channel
)
SELECT
  c.acquisition_channel                                            AS channel,
  c.signups,
  s.spend_usd,
  ROUND(SAFE_DIVIDE(s.spend_usd, c.signups), 2)                    AS cac_usd,
  ROUND(SAFE_DIVIDE(r.revenue_6m_usd, c.signups), 2)               AS revenue_per_user_6m_usd,
  ROUND(SAFE_DIVIDE(r.revenue_6m_usd, c.signups) - SAFE_DIVIDE(s.spend_usd, c.signups), 2) AS margin_per_user_6m_usd,
  ROUND(SAFE_DIVIDE(r.revenue_6m_usd, s.spend_usd), 2)             AS revenue_to_spend_ratio
FROM counts AS c
JOIN spend AS s ON s.channel = c.acquisition_channel
LEFT JOIN rev_6m AS r USING (acquisition_channel)
ORDER BY margin_per_user_6m_usd DESC;
