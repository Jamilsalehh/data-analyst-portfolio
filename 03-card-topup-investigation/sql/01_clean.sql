-- =====================================================================
-- 01_clean.sql  ·  BigQuery Standard SQL  ·  dataset: topups
-- One clean row per top-up attempt, with the fields the investigation needs.
-- =====================================================================

CREATE OR REPLACE VIEW topups.v_attempts AS
WITH dedup AS (
  -- the gateway webhook sometimes delivers the same attempt twice
  SELECT *
  FROM topups.topup_attempts
  WHERE TRUE   -- BigQuery wants a WHERE/GROUP BY next to QUALIFY
  QUALIFY ROW_NUMBER() OVER (PARTITION BY attempt_id ORDER BY attempted_at) = 1
)
SELECT
  d.attempt_id,
  CAST(d.attempted_at AS TIMESTAMP)                          AS attempted_at,
  DATE(CAST(d.attempted_at AS TIMESTAMP))                    AS attempt_date,
  d.account_id,
  DATE_DIFF(DATE(CAST(d.attempted_at AS TIMESTAMP)), CAST(a.created_at AS DATE), DAY) AS account_age_days,
  a.region,
  d.issuer,
  d.card_brand,
  COALESCE(d.card_currency, 'Not given')                     AS card_currency,
  d.gateway,
  d.amount_usd,
  CASE
    WHEN d.amount_usd <= 20   THEN '1) Up to $20'
    WHEN d.amount_usd <= 50   THEN '2) $21-50'
    WHEN d.amount_usd <= 100  THEN '3) $51-100'
    WHEN d.amount_usd <= 250  THEN '4) $101-250'
    WHEN d.amount_usd <= 500  THEN '5) $251-500'
    WHEN d.amount_usd <= 1000 THEN '6) $501-1,000'
    ELSE '7) Over $1,000'
  END                                                        AS amount_band,
  d.status = 'ACCEPTED'                                      AS accepted,
  d.failure_reason,
  -- 1st, 2nd, 3rd... attempt by this account on this day
  ROW_NUMBER() OVER (PARTITION BY d.account_id, DATE(CAST(d.attempted_at AS TIMESTAMP))
                     ORDER BY d.attempted_at)                AS attempt_no_that_day
FROM dedup AS d
LEFT JOIN topups.accounts AS a USING (account_id);


-- Quick checks after cleaning
SELECT
  (SELECT COUNT(*) FROM topups.topup_attempts)               AS raw_rows,
  (SELECT COUNT(*) FROM topups.v_attempts)                   AS clean_rows,
  (SELECT COUNTIF(card_currency = 'Not given') FROM topups.v_attempts) AS missing_currency,
  (SELECT COUNTIF(region IS NULL) FROM topups.v_attempts)    AS attempts_without_account;
