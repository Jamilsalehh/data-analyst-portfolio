-- =====================================================================
-- 02_find_the_problem.sql  ·  Is something actually broken, and since when?
-- =====================================================================

-- 1) Acceptance rate by card issuer: 1 Jul - 24 Aug vs 25 Aug - 12 Oct
SELECT
  issuer,
  COUNTIF(attempt_date <  '2026-08-25')                                                 AS attempts_before,
  ROUND(SAFE_DIVIDE(COUNTIF(accepted AND attempt_date <  '2026-08-25'),
                    COUNTIF(attempt_date <  '2026-08-25')) * 100, 1)                    AS acceptance_before_pct,
  COUNTIF(attempt_date >= '2026-08-25')                                                 AS attempts_after,
  ROUND(SAFE_DIVIDE(COUNTIF(accepted AND attempt_date >= '2026-08-25'),
                    COUNTIF(attempt_date >= '2026-08-25')) * 100, 1)                    AS acceptance_after_pct
FROM topups.v_attempts
GROUP BY issuer
ORDER BY acceptance_after_pct;


-- 2) Daily acceptance: Issuer 03 against every other issuer, around the break
SELECT
  attempt_date,
  ROUND(SAFE_DIVIDE(COUNTIF(accepted AND issuer = 'Issuer 03'), COUNTIF(issuer = 'Issuer 03')) * 100, 1)   AS issuer03_pct,
  ROUND(SAFE_DIVIDE(COUNTIF(accepted AND issuer != 'Issuer 03'), COUNTIF(issuer != 'Issuer 03')) * 100, 1) AS other_issuers_pct
FROM topups.v_attempts
WHERE attempt_date BETWEEN '2026-08-18' AND '2026-09-01'
GROUP BY attempt_date
ORDER BY attempt_date;


-- 3) Pin down the moment: last accepted and first declined Issuer 03 attempts around the break
SELECT
  MAX(IF(accepted, attempted_at, NULL))                       AS last_accepted_issuer03,
  (SELECT MIN(attempted_at) FROM topups.v_attempts
    WHERE issuer = 'Issuer 03' AND NOT accepted
      AND attempted_at > (SELECT MAX(attempted_at) FROM topups.v_attempts WHERE issuer = 'Issuer 03' AND accepted)
  )                                                           AS first_decline_after_that
FROM topups.v_attempts
WHERE issuer = 'Issuer 03';
