-- =====================================================================
-- 01_clean_views.sql  ·  BigQuery Standard SQL
-- Cleans the raw exports into views the dashboard and analysis use.
-- Dataset: contact_center  (tables: agents, calls_queue_hourly,
--                           calls_agent_daily, tickets)
-- =====================================================================

-- 1) Agent daily stats: drop re-imported duplicate rows, fix name formatting,
--    and label phone-system temp IDs that HR hasn't mapped yet.
CREATE OR REPLACE VIEW contact_center.v_agent_daily AS
WITH dedup AS (
  SELECT DISTINCT *            -- the same day was exported twice on a few dates
  FROM contact_center.calls_agent_daily
)
SELECT
  d.work_date,
  d.agent_id,
  COALESCE(a.agent_name, 'Unmapped (temp ID)') AS agent_name,   -- master name, not the export's spelling
  COALESCE(a.team, 'Unmapped')                 AS team,
  d.queue,
  d.logged_in_s,
  d.talk_s,
  d.not_ready_s,
  d.break_s,
  d.presented,
  d.answered,
  d.short_calls,
  d.transfers_out,
  a.agent_id IS NULL                           AS is_unmapped
FROM dedup AS d
LEFT JOIN contact_center.agents AS a USING (agent_id);


-- 2) Tickets: one status spelling, durations in minutes/hours, and a flag for
--    rows where the helpdesk recorded solved_at before created_at.
CREATE OR REPLACE VIEW contact_center.v_tickets AS
SELECT
  ticket_id,
  CAST(created_at AS TIMESTAMP)                         AS created_at,
  DATE(CAST(created_at AS TIMESTAMP))                   AS created_date,
  CAST(first_reply_at AS TIMESTAMP)                     AS first_reply_at,
  CAST(solved_at AS TIMESTAMP)                          AS solved_at,
  INITCAP(status)                                       AS status,
  entity,
  category,
  channel,
  assignee_id,
  satisfaction,
  reopened,
  TIMESTAMP_DIFF(CAST(first_reply_at AS TIMESTAMP), CAST(created_at AS TIMESTAMP), MINUTE) AS first_reply_min,
  CASE
    WHEN CAST(solved_at AS TIMESTAMP) < CAST(created_at AS TIMESTAMP) THEN NULL   -- bad timestamp, excluded
    ELSE TIMESTAMP_DIFF(CAST(solved_at AS TIMESTAMP), CAST(created_at AS TIMESTAMP), MINUTE) / 60.0
  END                                                   AS resolution_h,
  CAST(solved_at AS TIMESTAMP) < CAST(created_at AS TIMESTAMP) AS bad_timestamp
FROM contact_center.tickets;


-- 3) Data-quality summary (what the cleaning step changed)
SELECT 'duplicate agent-day rows removed' AS check_name,
       (SELECT COUNT(*) FROM contact_center.calls_agent_daily)
     - (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM contact_center.calls_agent_daily)) AS row_count
UNION ALL
SELECT 'agent-day rows with unmapped temp IDs',
       (SELECT COUNTIF(is_unmapped) FROM contact_center.v_agent_daily)
UNION ALL
SELECT 'tickets with non-standard status casing',
       (SELECT COUNTIF(status != INITCAP(status)) FROM contact_center.tickets)
UNION ALL
SELECT 'tickets with solved_at before created_at',
       (SELECT COUNTIF(bad_timestamp) FROM contact_center.v_tickets);
