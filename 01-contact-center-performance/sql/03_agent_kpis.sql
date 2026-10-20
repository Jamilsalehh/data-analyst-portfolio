-- =====================================================================
-- 03_agent_kpis.sql  ·  BigQuery Standard SQL
-- Agent-level productivity and the staffing link behind the summer dip.
-- Uses the cleaned view v_agent_daily from 01_clean_views.sql.
-- =====================================================================

-- 1) Agent scorecard per month: volume, calls per logged-in hour, occupancy,
--    and rank inside their team.  Occupancy = talk time / time available
--    to take calls (logged in minus breaks and not-ready time).
WITH monthly AS (
  SELECT
    DATE_TRUNC(work_date, MONTH)                                   AS month,
    agent_id,
    agent_name,
    team,
    COUNT(DISTINCT work_date)                                      AS days_worked,
    SUM(answered)                                                  AS answered,
    SUM(presented)                                                 AS presented,
    SUM(logged_in_s) / 3600                                        AS logged_in_h,
    SAFE_DIVIDE(SUM(talk_s), SUM(logged_in_s - break_s - not_ready_s)) AS occupancy
  FROM contact_center.v_agent_daily
  WHERE NOT is_unmapped
  GROUP BY month, agent_id, agent_name, team
)
SELECT
  month,
  team,
  agent_name,
  days_worked,
  answered,
  ROUND(SAFE_DIVIDE(answered, presented) * 100, 1)                 AS pickup_rate_pct,
  ROUND(SAFE_DIVIDE(answered, logged_in_h), 1)                     AS calls_per_logged_hour,
  ROUND(occupancy * 100, 1)                                        AS occupancy_pct,
  RANK() OVER (PARTITION BY month, team ORDER BY answered DESC)    AS rank_in_team
FROM monthly
ORDER BY month, team, rank_in_team;


-- 2) Staffing vs. service: App Support agents on the phones each day
--    against that day's answer rate. Bucketed so the threshold is visible.
WITH staff AS (
  SELECT work_date, COUNT(DISTINCT agent_id) AS agents_on_phones
  FROM contact_center.v_agent_daily
  WHERE queue = 'App Support'
  GROUP BY work_date
),
service AS (
  SELECT call_date AS work_date,
         SUM(offered) AS offered,
         SAFE_DIVIDE(SUM(answered), SUM(offered)) AS answer_rate
  FROM contact_center.calls_queue_hourly
  WHERE queue = 'App Support'
  GROUP BY call_date
)
SELECT
  CASE
    WHEN agents_on_phones <= 15 THEN '15 or fewer'
    WHEN agents_on_phones <= 17 THEN '16-17'
    WHEN agents_on_phones <= 19 THEN '18-19'
    ELSE '20+'
  END                                            AS staffing_bucket,
  COUNT(*)                                       AS weekdays,
  ROUND(AVG(answer_rate) * 100, 1)               AS avg_answer_rate_pct
FROM staff
JOIN service USING (work_date)
WHERE FORMAT_DATE('%a', work_date) NOT IN ('Sat', 'Sun')   -- weekdays only: weekends have far fewer calls
GROUP BY staffing_bucket
ORDER BY staffing_bucket;


-- 3) Headcount on the App Support team by month (who left, who joined)
SELECT
  DATE_TRUNC(work_date, MONTH)        AS month,
  COUNT(DISTINCT agent_id)            AS app_support_agents_active
FROM contact_center.v_agent_daily
WHERE team = 'App Support'
GROUP BY month
ORDER BY month;
