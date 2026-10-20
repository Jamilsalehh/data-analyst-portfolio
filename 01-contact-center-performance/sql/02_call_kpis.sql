-- =====================================================================
-- 02_call_kpis.sql  ·  BigQuery Standard SQL
-- Queue-level phone KPIs: answer rate, abandon rate, service level, ASA.
-- =====================================================================

-- 1) Monthly KPIs per queue
SELECT
  queue,
  DATE_TRUNC(call_date, MONTH)                                     AS month,
  SUM(offered)                                                     AS offered,
  SUM(answered)                                                    AS answered,
  SUM(abandoned)                                                   AS abandoned,
  ROUND(SAFE_DIVIDE(SUM(answered), SUM(offered)) * 100, 1)          AS answer_rate_pct,
  ROUND(SAFE_DIVIDE(SUM(abandoned), SUM(offered)) * 100, 1)         AS abandon_rate_pct,
  ROUND(SAFE_DIVIDE(SUM(answered_within_20s), SUM(offered)) * 100, 1) AS service_level_20s_pct,
  ROUND(SAFE_DIVIDE(SUM(total_answer_delay_s), SUM(answered)), 1)   AS avg_speed_of_answer_s
FROM contact_center.calls_queue_hourly
GROUP BY queue, month
ORDER BY queue, month;


-- 2) When do callers give up?  Abandon rate by weekday x hour (App Support)
SELECT
  FORMAT_DATE('%a', call_date)                                     AS weekday,
  EXTRACT(DAYOFWEEK FROM call_date)                                AS weekday_order,
  call_hour,
  SUM(offered)                                                     AS offered,
  ROUND(SAFE_DIVIDE(SUM(abandoned), SUM(offered)) * 100, 1)         AS abandon_rate_pct
FROM contact_center.calls_queue_hourly
WHERE queue = 'App Support'
GROUP BY weekday, weekday_order, call_hour
ORDER BY weekday_order, call_hour;


-- 3) Lunch-hour effect: 12:00-13:59 vs the rest of the day, per queue
SELECT
  queue,
  IF(call_hour IN (12, 13), 'Lunch (12-14)', 'Rest of day')         AS period,
  SUM(offered)                                                     AS offered,
  SUM(abandoned)                                                   AS abandoned,
  ROUND(SAFE_DIVIDE(SUM(abandoned), SUM(offered)) * 100, 1)         AS abandon_rate_pct
FROM contact_center.calls_queue_hourly
GROUP BY queue, period
ORDER BY queue, period;


-- 4) Month-over-month change in App Support answer rate (window function)
WITH m AS (
  SELECT DATE_TRUNC(call_date, MONTH) AS month,
         SAFE_DIVIDE(SUM(answered), SUM(offered)) AS answer_rate
  FROM contact_center.calls_queue_hourly
  WHERE queue = 'App Support'
  GROUP BY month
)
SELECT
  month,
  ROUND(answer_rate * 100, 1)                                            AS answer_rate_pct,
  ROUND((answer_rate - LAG(answer_rate) OVER (ORDER BY month)) * 100, 1) AS change_vs_prev_month_pts
FROM m
ORDER BY month;
