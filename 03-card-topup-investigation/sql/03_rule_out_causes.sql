-- =====================================================================
-- 03_rule_out_causes.sql  ·  Gateway? Amount? Currency? Card brand? New users?
-- Every query looks only at Issuer 03 attempts after the break (25 Aug 09:40).
-- =====================================================================

-- 1) Is it one gateway?  If the failure shows up on every gateway, the gateway isn't the cause.
SELECT
  gateway,
  COUNT(*)                                                     AS attempts,
  COUNTIF(accepted)                                            AS accepted,
  STRING_AGG(DISTINCT failure_reason, ', ' ORDER BY failure_reason) AS failure_reasons_seen
FROM topups.v_attempts
WHERE issuer = 'Issuer 03' AND attempted_at >= '2026-08-25 09:40:00'
GROUP BY gateway
ORDER BY attempts DESC;


-- 2) Failure reasons by gateway (the wording differs, the result doesn't)
SELECT
  gateway,
  failure_reason,
  COUNT(*)                                                     AS attempts,
  ROUND(COUNT(*) * 100 / SUM(COUNT(*)) OVER (PARTITION BY gateway), 1) AS share_within_gateway_pct
FROM topups.v_attempts
WHERE issuer = 'Issuer 03' AND attempted_at >= '2026-08-25 09:40:00'
GROUP BY gateway, failure_reason
ORDER BY gateway, attempts DESC;


-- 3) Is it large amounts hitting a limit?  (No: small top-ups fail too)
SELECT
  amount_band,
  COUNT(*)                                                     AS attempts,
  ROUND(SAFE_DIVIDE(COUNTIF(accepted), COUNT(*)) * 100, 1)     AS acceptance_pct
FROM topups.v_attempts
WHERE issuer = 'Issuer 03' AND attempted_at >= '2026-08-25 09:40:00'
GROUP BY amount_band
ORDER BY amount_band;


-- 4) Card currency, card brand and account age, all in one pass
SELECT 'card_currency' AS dimension, card_currency AS dim_value, COUNT(*) AS attempts,
       ROUND(SAFE_DIVIDE(COUNTIF(accepted), COUNT(*)) * 100, 1) AS acceptance_pct
FROM topups.v_attempts
WHERE issuer = 'Issuer 03' AND attempted_at >= '2026-08-25 09:40:00'
GROUP BY dim_value
UNION ALL
SELECT 'card_brand', card_brand, COUNT(*), ROUND(SAFE_DIVIDE(COUNTIF(accepted), COUNT(*)) * 100, 1)
FROM topups.v_attempts
WHERE issuer = 'Issuer 03' AND attempted_at >= '2026-08-25 09:40:00'
GROUP BY card_brand
UNION ALL
SELECT 'account_age', IF(account_age_days <= 30, 'New (30 days or less)', 'Older'), COUNT(*),
       ROUND(SAFE_DIVIDE(COUNTIF(accepted), COUNT(*)) * 100, 1)
FROM topups.v_attempts
WHERE issuer = 'Issuer 03' AND attempted_at >= '2026-08-25 09:40:00'
GROUP BY 2
ORDER BY dimension, dim_value;


-- 5) Control check: the same gateways keep working for every other issuer after the break
SELECT
  gateway,
  ROUND(SAFE_DIVIDE(COUNTIF(accepted), COUNT(*)) * 100, 1)     AS other_issuers_acceptance_pct
FROM topups.v_attempts
WHERE issuer != 'Issuer 03' AND attempted_at >= '2026-08-25 09:40:00'
GROUP BY gateway
ORDER BY gateway;
