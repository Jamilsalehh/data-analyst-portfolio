-- =====================================================================
-- 04_customer_impact.sql  ·  Who is affected, what do they do, what does it cost?
-- =====================================================================

-- 1) Customers hit, attempts per customer, and money that didn't come in
WITH hit AS (
  SELECT account_id, COUNT(*) AS attempts, SUM(amount_usd) AS amount_tried
  FROM topups.v_attempts
  WHERE issuer = 'Issuer 03' AND attempted_at >= '2026-08-25 09:40:00'
  GROUP BY account_id
)
SELECT
  COUNT(*)                                       AS customers_affected,
  SUM(attempts)                                  AS failed_attempts,
  ROUND(AVG(attempts), 2)                        AS avg_attempts_per_customer,
  COUNTIF(attempts >= 3)                         AS customers_with_3plus_attempts,
  MAX(attempts)                                  AS most_attempts_by_one_customer
FROM hit;


-- 2) After failing with an Issuer 03 card, did the customer top up another way the same day?
WITH fails AS (
  SELECT account_id, attempt_date, MIN(attempted_at) AS first_fail_at
  FROM topups.v_attempts
  WHERE issuer = 'Issuer 03' AND attempted_at >= '2026-08-25 09:40:00'
  GROUP BY account_id, attempt_date
),
outcome AS (
  SELECT
    f.account_id,
    f.attempt_date,
    LOGICAL_OR(v.accepted AND v.issuer != 'Issuer 03') AS saved_by_other_card
  FROM fails AS f
  LEFT JOIN topups.v_attempts AS v
    ON v.account_id = f.account_id
   AND v.attempted_at > f.first_fail_at
   AND v.attempt_date = f.attempt_date
  GROUP BY f.account_id, f.attempt_date
)
SELECT
  COUNT(*)                                                         AS customer_days_with_a_failure,
  COUNTIF(saved_by_other_card)                                     AS topped_up_with_another_card,
  ROUND(SAFE_DIVIDE(COUNTIF(saved_by_other_card), COUNT(*)) * 100, 1) AS saved_pct,
  ROUND(SAFE_DIVIDE(COUNTIF(NOT COALESCE(saved_by_other_card, FALSE)), COUNT(*)) * 100, 1) AS gave_up_pct
FROM outcome;


-- 3) Money: amount customers tried to load with Issuer 03 cards after the break.
--    "Intended" counts each customer-day once at its largest attempt, so retries aren't double counted.
WITH per_day AS (
  SELECT account_id, attempt_date, MAX(amount_usd) AS intended_usd
  FROM topups.v_attempts
  WHERE issuer = 'Issuer 03' AND attempted_at >= '2026-08-25 09:40:00'
  GROUP BY account_id, attempt_date
)
SELECT
  ROUND(SUM(intended_usd), 0)                    AS intended_topups_usd,
  ROUND(SUM(intended_usd) * 0.015, 0)            AS lost_fee_revenue_usd_at_1_5pct,
  ROUND(SUM(intended_usd) / DATE_DIFF(DATE '2026-10-12', DATE '2026-08-25', DAY), 0) AS intended_usd_per_day
FROM per_day;


-- 4) Weekly view for the incident report
SELECT
  DATE_TRUNC(attempt_date, WEEK(MONDAY))                           AS week,
  COUNTIF(issuer = 'Issuer 03')                                    AS issuer03_attempts,
  COUNTIF(issuer = 'Issuer 03' AND accepted)                       AS issuer03_accepted,
  COUNT(DISTINCT IF(issuer = 'Issuer 03', account_id, NULL))       AS issuer03_customers
FROM topups.v_attempts
WHERE attempt_date >= '2026-08-03'
GROUP BY week
ORDER BY week;
