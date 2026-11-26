-- Member 1: independent dashboard data only. Install after ORM table creation.
-- No assumptions about unfinished class/attendance or PT tables are embedded.
-- Each member appears once, including members with no goals or measurements.
CREATE OR REPLACE VIEW member_dashboard AS
SELECT m.member_id,
       latest.metric_id AS latest_metric_id,
       latest.recorded_at,
       latest.weight_kg,
       latest.height_cm,
       latest.heart_rate_bpm,
       (SELECT count(*) FROM fitness_goals AS g
        WHERE g.member_id = m.member_id AND g.status = 'active') AS active_goal_count,
       weight.weight_kg AS latest_weight_kg,
       weight.recorded_at AS weight_recorded_at
FROM members AS m
LEFT JOIN LATERAL (
    SELECT h.metric_id, h.recorded_at, h.weight_kg, h.height_cm, h.heart_rate_bpm
    FROM health_metrics AS h
    WHERE h.member_id = m.member_id
    ORDER BY h.recorded_at DESC, h.metric_id DESC
    LIMIT 1
) AS latest ON true
LEFT JOIN LATERAL (
    SELECT h.weight_kg, h.recorded_at
    FROM health_metrics AS h
    WHERE h.member_id = m.member_id AND h.weight_kg IS NOT NULL
    ORDER BY h.recorded_at DESC, h.metric_id DESC
    LIMIT 1
) AS weight ON true;
