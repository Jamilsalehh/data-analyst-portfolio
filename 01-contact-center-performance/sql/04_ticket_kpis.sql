-- =====================================================================
-- 04_ticket_kpis.sql  ·  BigQuery Standard SQL
-- Helpdesk KPIs: volume, first reply time, resolution time, satisfaction.
-- Uses the cleaned view v_tickets from 01_clean_views.sql.
-- =====================================================================

-- 1) Monthly ticket KPIs (all teams)
SELECT
  DATE_TRUNC(created_date, MONTH)                                     AS month,
  COUNT(*)                                                            AS created,
  COUNTIF(status IN ('Solved', 'Closed'))                             AS solved,
  APPROX_QUANTILES(first_reply_min, 100)[OFFSET(50)]                  AS median_first_reply_min,
  ROUND(AVG(resolution_h), 1)                                         AS avg_resolution_h,
  ROUND(SAFE_DIVIDE(COUNTIF(satisfaction = 'good'),
                    COUNTIF(satisfaction IS NOT NULL)) * 100, 1)      AS csat_pct
FROM contact_center.v_tickets
GROUP BY month
ORDER BY month;


-- 2) Team comparison: where is the wait longest?
SELECT
  entity                                                              AS team,
  COUNT(*)                                                            AS tickets,
  APPROX_QUANTILES(first_reply_min, 100)[OFFSET(50)]                  AS median_first_reply_min,
  APPROX_QUANTILES(resolution_h, 100)[OFFSET(50)]                     AS median_resolution_h,
  ROUND(SAFE_DIVIDE(COUNTIF(satisfaction = 'good'),
                    COUNTIF(satisfaction IS NOT NULL)) * 100, 1)      AS csat_pct
FROM contact_center.v_tickets
GROUP BY team
ORDER BY tickets DESC;


-- 3) Does a slow first reply hurt satisfaction?  CSAT by first-reply bucket
SELECT
  CASE
    WHEN first_reply_min <= 60  THEN '1) within 1h'
    WHEN first_reply_min <= 120 THEN '2) 1-2h'
    WHEN first_reply_min <= 240 THEN '3) 2-4h'
    WHEN first_reply_min <= 480 THEN '4) 4-8h'
    ELSE '5) over 8h'
  END                                                                 AS first_reply_bucket,
  COUNTIF(satisfaction IS NOT NULL)                                   AS rated_tickets,
  ROUND(SAFE_DIVIDE(COUNTIF(satisfaction = 'good'),
                    COUNTIF(satisfaction IS NOT NULL)) * 100, 1)      AS csat_pct
FROM contact_center.v_tickets
WHERE first_reply_min IS NOT NULL
GROUP BY first_reply_bucket
ORDER BY first_reply_bucket;


-- 4) Share of tickets answered within 4 hours, by month (the target I'd propose)
SELECT
  DATE_TRUNC(created_date, MONTH)                                     AS month,
  ROUND(SAFE_DIVIDE(COUNTIF(first_reply_min <= 240),
                    COUNTIF(first_reply_min IS NOT NULL)) * 100, 1)   AS replied_within_4h_pct
FROM contact_center.v_tickets
GROUP BY month
ORDER BY month;


-- 5) Top categories driving After-Sales volume, with their wait times
SELECT
  category,
  COUNT(*)                                                            AS tickets,
  ROUND(COUNT(*) * 100 / SUM(COUNT(*)) OVER (), 1)                    AS share_pct,
  APPROX_QUANTILES(first_reply_min, 100)[OFFSET(50)]                  AS median_first_reply_min
FROM contact_center.v_tickets
WHERE entity = 'After-Sales'
GROUP BY category
ORDER BY tickets DESC;
