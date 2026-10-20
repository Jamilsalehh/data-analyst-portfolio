-- =====================================================================
-- 02_cohort_retention.sql  ·  Classic monthly cohort retention
-- Retention in month N = users from the cohort who made a completed
-- transaction in month N after signup / all users who signed up that month.
-- =====================================================================

-- 1) Long format (feed this to a heatmap): cohort x month_number
WITH cohort_size AS (
  SELECT cohort_month, COUNT(*) AS users
  FROM wallet.user_summary
  GROUP BY cohort_month
),
active AS (
  SELECT cohort_month, month_number, COUNT(DISTINCT user_id) AS active_users
  FROM wallet.user_month
  GROUP BY cohort_month, month_number
)
SELECT
  a.cohort_month,
  c.users                                              AS cohort_size,
  a.month_number,
  a.active_users,
  ROUND(a.active_users / c.users * 100, 1)             AS retention_pct
FROM active AS a
JOIN cohort_size AS c USING (cohort_month)
ORDER BY a.cohort_month, a.month_number;


-- 2) Wide format (one row per cohort, M0..M6), the classic triangle
WITH base AS (
  SELECT s.cohort_month, COUNT(*) AS users
  FROM wallet.user_summary AS s
  GROUP BY s.cohort_month
),
m AS (
  SELECT cohort_month, month_number, COUNT(DISTINCT user_id) AS active_users
  FROM wallet.user_month
  GROUP BY cohort_month, month_number
)
SELECT
  b.cohort_month,
  b.users,
  ROUND(MAX(IF(m.month_number = 0, m.active_users, NULL)) / b.users * 100, 0) AS m0,
  ROUND(MAX(IF(m.month_number = 1, m.active_users, NULL)) / b.users * 100, 0) AS m1,
  ROUND(MAX(IF(m.month_number = 2, m.active_users, NULL)) / b.users * 100, 0) AS m2,
  ROUND(MAX(IF(m.month_number = 3, m.active_users, NULL)) / b.users * 100, 0) AS m3,
  ROUND(MAX(IF(m.month_number = 4, m.active_users, NULL)) / b.users * 100, 0) AS m4,
  ROUND(MAX(IF(m.month_number = 5, m.active_users, NULL)) / b.users * 100, 0) AS m5,
  ROUND(MAX(IF(m.month_number = 6, m.active_users, NULL)) / b.users * 100, 0) AS m6
FROM base AS b
LEFT JOIN m USING (cohort_month)
GROUP BY b.cohort_month, b.users
ORDER BY b.cohort_month;
