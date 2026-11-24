-- Where would a new branch help most? Clients who live more than 10 km from every office, and the suburb that would put the
-- most of them within 10 km of a new office (the Principal's branch question, the "where" half).
-- demand      = Australian matters opened in the last 12 months, by the client's suburb (sample data);
-- underserved = suburbs more than 10 km from the nearest existing office (straight line);
-- candidate   = any suburb; it wins the underserved matters within 10 km of it that are closer to it than to today's offices.
-- Distance: flat-earth approximation at Sydney's latitude (1° lat = 110.57 km, 1° lon = 92.45 km), compared squared to avoid SQRT;
-- within 0.5% of the great-circle distance at this scale.
-- Techniques: CTEs, self cross join, conditional aggregation, RANK window, CASE.
WITH asof AS (
    SELECT date(meta_value) AS as_of, date(meta_value, '-1 year', '+1 day') AS ltm_start
    FROM etl_meta WHERE meta_key = 'as_of_date'
),
demand AS (        -- matters opened in the last 12 months, by client suburb
    SELECT m.suburb_key, COUNT(*) AS matters, SUM(p.estimated_value) AS est_value
    FROM dim_matter m
    JOIN dim_date d ON d.date_key = m.opened_date_key
    JOIN fact_matter_position p ON p.matter_key = m.matter_key
    CROSS JOIN asof a
    WHERE m.suburb_key IS NOT NULL AND d.full_date BETWEEN a.ltm_start AND a.as_of
    GROUP BY m.suburb_key
),
pairs AS (         -- every candidate suburb against every client suburb
    SELECT c.suburb_key AS cand_key, s.suburb_key, s.km_to_nearest_branch,
           ((c.latitude - s.latitude) * 110.57) * ((c.latitude - s.latitude) * 110.57)
         + ((c.longitude - s.longitude) * 92.45) * ((c.longitude - s.longitude) * 92.45) AS km2
    FROM dim_suburb c CROSS JOIN dim_suburb s
),
won AS (
    SELECT p.cand_key,
           SUM(CASE WHEN p.km_to_nearest_branch > 10 AND p.km2 <= 100 AND p.km2 < p.km_to_nearest_branch * p.km_to_nearest_branch
                    THEN d.matters ELSE 0 END) AS matters_won,
           SUM(CASE WHEN p.km_to_nearest_branch > 10 AND p.km2 <= 100 AND p.km2 < p.km_to_nearest_branch * p.km_to_nearest_branch
                    THEN d.est_value ELSE 0 END) AS est_value_won,
           SUM(CASE WHEN p.km_to_nearest_branch > 10 AND p.km2 <= 100 AND p.km2 < p.km_to_nearest_branch * p.km_to_nearest_branch
                    THEN 1 ELSE 0 END) AS suburbs_won
    FROM pairs p JOIN demand d ON d.suburb_key = p.suburb_key
    GROUP BY p.cand_key
)
SELECT c.suburb AS candidate_site,
       w.matters_won AS underserved_matters_ltm,
       ROUND(w.est_value_won, 0) AS est_value_ltm,
       w.suburbs_won AS suburbs_covered,
       b.branch_name AS nearest_office,
       c.km_to_nearest_branch AS km_to_nearest_office,
       RANK() OVER (ORDER BY w.matters_won DESC, w.est_value_won DESC) AS site_rank
FROM won w
JOIN dim_suburb c ON c.suburb_key = w.cand_key
JOIN dim_branch b ON b.branch_key = c.nearest_branch_key
WHERE w.matters_won > 0
ORDER BY site_rank, candidate_site
LIMIT 10;
