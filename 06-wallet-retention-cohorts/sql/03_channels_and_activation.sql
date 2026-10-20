-- =====================================================================
-- 03_channels_and_activation.sql  ·  Who stays, and what predicts it?
-- Month-3 retention needs 3 full months of history, so only cohorts up to
-- Jun 2026 are used for M3 numbers.
-- =====================================================================

-- 1) Month-3 retention by acquisition channel
WITH eligible AS (
  SELECT * FROM wallet.user_summary WHERE cohort_month <= '2026-06-01'
),
m3 AS (
  SELECT DISTINCT user_id FROM wallet.user_month WHERE month_number = 3
)
SELECT
  e.acquisition_channel,
  COUNT(*)                                                         AS users,
  ROUND(COUNTIF(e.activated_14d) / COUNT(*) * 100, 1)              AS activated_pct,
  ROUND(COUNTIF(m3.user_id IS NOT NULL) / COUNT(*) * 100, 1)       AS m3_retention_pct
FROM eligible AS e
LEFT JOIN m3 USING (user_id)
GROUP BY e.acquisition_channel
ORDER BY m3_retention_pct DESC;


-- 2) The activation effect: month-3 retention for users who did / didn't pay a bill
--    or a merchant in their first 14 days, inside each channel (so channel mix can't explain it)
WITH eligible AS (
  SELECT * FROM wallet.user_summary WHERE cohort_month <= '2026-06-01' AND ever_transacted
),
m3 AS (
  SELECT DISTINCT user_id FROM wallet.user_month WHERE month_number = 3
)
SELECT
  e.acquisition_channel,
  ROUND(SAFE_DIVIDE(COUNTIF(e.activated_14d AND m3.user_id IS NOT NULL), COUNTIF(e.activated_14d)) * 100, 1)         AS m3_if_activated_pct,
  ROUND(SAFE_DIVIDE(COUNTIF(NOT e.activated_14d AND m3.user_id IS NOT NULL), COUNTIF(NOT e.activated_14d)) * 100, 1) AS m3_if_not_activated_pct
FROM eligible AS e
LEFT JOIN m3 USING (user_id)
GROUP BY e.acquisition_channel
ORDER BY e.acquisition_channel;


-- 3) Overall activation effect (one line for the summary)
WITH eligible AS (
  SELECT * FROM wallet.user_summary WHERE cohort_month <= '2026-06-01' AND ever_transacted
),
m3 AS (
  SELECT DISTINCT user_id FROM wallet.user_month WHERE month_number = 3
)
SELECT
  e.activated_14d,
  COUNT(*)                                                         AS users,
  ROUND(COUNTIF(m3.user_id IS NOT NULL) / COUNT(*) * 100, 1)       AS m3_retention_pct
FROM eligible AS e
LEFT JOIN m3 USING (user_id)
GROUP BY e.activated_14d
ORDER BY e.activated_14d DESC;
