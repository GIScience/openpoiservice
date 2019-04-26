EXPLAIN ANALYZE


SELECT COUNT(blubb.*) FROM (
SELECT anon_1.osm_id,
anon_1.osm_type,
st_distance(anon_1.geom, st_geogfromtext('POLYGON ((8.74189636230469 53.07144289415349, 8.814767341613772 53.07144289415349, 8.814767341613772 53.09106030870385, 8.74189636230469 53.09106030870385, 8.74189636230469 53.07144289415349))')),
st_asbinary(anon_1.geom),
array_agg(ops_planet_pois_tags.KEY),
array_agg(ops_planet_pois_tags.value),
array_agg(ops_planet_pois_categories.category)
FROM (
    SELECT ops_planet_pois.uuid,
    ops_planet_pois.osm_id,
    ops_planet_pois.osm_type,
    ops_planet_pois.geom
    FROM   ops_planet_pois
    WHERE st_dwithin(st_buffer(st_geogfromtext('POLYGON ((8.74189636230469 53.07144289415349, 8.814767341613772 53.07144289415349, 8.814767341613772 53.09106030870385, 8.74189636230469 53.09106030870385, 8.74189636230469 53.07144289415349))'), 0), ops_planet_pois.geom, 0)
) AS anon_1
LEFT OUTER JOIN ops_planet_pois_tags
ON              anon_1.uuid = ops_planet_pois_tags.uuid
LEFT OUTER JOIN ops_planet_pois_categories
ON              anon_1.uuid = ops_planet_pois_categories.uuid
GROUP BY        anon_1.uuid,
                anon_1.osm_id,
                anon_1.osm_type,
                anon_1.geom
                ) as blubb;


SELECT COUNT(blubb.*) FROM (
SELECT ops_planet_pois.uuid,
    ops_planet_pois.osm_id,
    ops_planet_pois.osm_type,
    ops_planet_pois.geom
    FROM   ops_planet_pois
    WHERE st_dwithin(st_buffer(st_geogfromtext('POLYGON ((8.74189636230469 53.07144289415349, 8.814767341613772 53.07144289415349, 8.814767341613772 53.09106030870385, 8.74189636230469 53.09106030870385, 8.74189636230469 53.07144289415349))'), 0), ops_planet_pois.geom, 0)

) as blubb;



 GroupAggregate  (cost=28.79..29.07 rows=1 width=197) (actual time=479.338..566.957 rows=2738 loops=1)
   Group Key: ops_planet_pois.uuid
   ->  Sort  (cost=28.79..28.79 rows=1 width=91) (actual time=479.058..500.780 rows=4700 loops=1)
         Sort Key: ops_planet_pois.uuid
         Sort Method: quicksort  Memory: 916kB
         ->  Nested Loop Left Join  (cost=4.87..28.78 rows=1 width=91) (actual time=0.376..445.046 rows=4700 loops=1)
               ->  Nested Loop Left Join  (cost=4.58..20.46 rows=1 width=87) (actual time=0.343..256.662 rows=4644 loops=1)
                     ->  Index Scan using idx_ops_planet_pois_geom on ops_planet_pois  (cost=0.28..8.67 rows=1 width=61) (actual time=0.298..80.411 rows=2738 loops=1)
                           Index Cond: (geom && '0103000020E61000000100000005000000723D0AD7D97B2140DEF56E0A25894A40723D0AD7D97B214061EC3BDDA78B4A40F7285C2F29A1214061EC3BDDA78B4A40F7285C2F29A12140DEF56E0A25894A40723D0AD7D97B2140DEF56E0A25894A40'::geography)
                           Filter: (('0103000020E61000000100000005000000723D0AD7D97B2140DEF56E0A25894A40723D0AD7D97B214061EC3BDDA78B4A40F7285C2F29A1214061EC3BDDA78B4A40F7285C2F29A12140DEF56E0A25894A40723D0AD7D97B2140DEF56E0A25894A40'::geography && _st_expand(geom, '0'::double precision)) AND _st_dwithin('0103000020E61000000100000005000000723D0AD7D97B2140DEF56E0A25894A40723D0AD7D97B214061EC3BDDA78B4A40F7285C2F29A1214061EC3BDDA78B4A40F7285C2F29A12140DEF56E0A25894A40723D0AD7D97B2140DEF56E0A25894A40'::geography, geom, '0'::double precision, true))
                           Rows Removed by Filter: 121
                     ->  Bitmap Heap Scan on ops_planet_pois_tags  (cost=4.30..11.77 rows=2 width=43) (actual time=0.024..0.032 rows=1 loops=2738)
                           Recheck Cond: (ops_planet_pois.uuid = uuid)
                           Heap Blocks: exact=1820
                           ->  Bitmap Index Scan on ix_ops_planet_pois_tags_uuid  (cost=0.00..4.30 rows=2 width=0) (actual time=0.011..0.011 rows=1 loops=2738)
                                 Index Cond: (ops_planet_pois.uuid = uuid)
               ->  Index Scan using ix_ops_planet_pois_categories_uuid on ops_planet_pois_categories  (cost=0.29..8.30 rows=1 width=21) (actual time=0.010..0.016 rows=1 loops=4644)
                     Index Cond: (ops_planet_pois.uuid = uuid)
 Planning time: 10.619 ms
 Execution time: 580.125 ms







EXPLAIN ANALYZE SELECT anon_1.posmid, anon_1.osm_type, anon_1.category, st_distance(anon_1.geom, st_geogfromtext('POLYGON ((8.74189636230469 53.07144289415349, 8.814767341613772 53.07144289415349, 8.814767341613772 53.09106030870385, 8.74189636230469 53.09106030870385, 8.74189636230469 53.07144289415349))')), anon_1.tosmid, anon_1.KEY, anon_1.value, st_asbinary(anon_1.geom)
FROM (
SELECT ops_planet_pois.uuid,
ops_planet_pois.osm_id as posmid,
ops_planet_pois.osm_type,
ops_planet_pois.category,
ops_planet_pois.geom,
ops_planet_pois_tags.osm_id as tosmid,
ops_planet_pois_tags.KEY,
ops_planet_pois_tags.value
FROM ops_planet_pois
left outer join ops_planet_pois_tags
ON ops_planet_pois.uuid = ops_planet_pois_tags.uuid
WHERE st_dwithin(st_buffer(st_geogfromtext('POLYGON ((8.74189636230469 53.07144289415349, 8.814767341613772 53.07144289415349, 8.814767341613772 53.09106030870385, 8.74189636230469 53.09106030870385, 8.74189636230469 53.07144289415349))'), 0), ops_planet_pois.geom, 0)
)
AS anon_1;



EXPLAIN ANALYZE SELECT anon_1.posmid, anon_1.osm_type, anon_1.category, st_distance(anon_1.geom, st_geogfromtext('POLYGON ((8.74189636230469 53.07144289415349, 8.814767341613772 53.07144289415349, 8.814767341613772 53.09106030870385, 8.74189636230469 53.09106030870385, 8.74189636230469 53.07144289415349))')), anon_1.tosmid, anon_1.KEY, anon_1.value, ST_AsGeoJSON(anon_1.geom)::json
FROM (
SELECT ops_planet_pois.uuid,
ops_planet_pois.osm_id as posmid,
ops_planet_pois.osm_type,
ops_planet_pois.category,
ops_planet_pois.geom,
ops_planet_pois_tags.osm_id as tosmid,
ops_planet_pois_tags.KEY,
ops_planet_pois_tags.value
FROM ops_planet_pois
left outer join ops_planet_pois_tags
ON ops_planet_pois.uuid = ops_planet_pois_tags.uuid
WHERE st_dwithin(st_buffer(st_geogfromtext('POLYGON ((8.74189636230469 53.07144289415349, 8.814767341613772 53.07144289415349, 8.814767341613772 53.09106030870385, 8.74189636230469 53.09106030870385, 8.74189636230469 53.07144289415349))'), 0), ops_planet_pois.geom, 0)
)
AS anon_1;








               QUERY PLAN
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 Hash Right Join  (cost=8.83..336320.09 rows=1 width=120) (actual time=998.644..3840.003 rows=4766 loops=1)
   Hash Cond: (ops_planet_pois_tags.uuid = ops_planet_pois.uuid)
   ->  Seq Scan on ops_planet_pois_tags  (cost=0.00..294848.00 rows=11056800 width=104) (actual time=0.070..1726.433 rows=16887559 loops=1)
   ->  Hash  (cost=8.81..8.81 rows=1 width=65) (actual time=31.450..31.450 rows=2807 loops=1)
         Buckets: 4096 (originally 1024)  Batches: 1 (originally 1)  Memory Usage: 290kB
         ->  Index Scan using idx_ops_planet_pois_geom on ops_planet_pois  (cost=0.42..8.81 rows=1 width=65) (actual time=0.380..30.480 rows=2807 loops=1)
               Index Cond: (geom && '0103000020E61000000100000005000000723D0AD7D97B2140DEF56E0A25894A40723D0AD7D97B21405FEC3BDDA78B4A40F7285C2F29A121405FEC3BDDA78B4A40F7285C2F29A12140DDF56E0A25894A40723D0AD7D97B2140DEF56E0A25894A40'::geography)
               Filter: (('0103000020E61000000100000005000000723D0AD7D97B2140DEF56E0A25894A40723D0AD7D97B21405FEC3BDDA78B4A40F7285C2F29A121405FEC3BDDA78B4A40F7285C2F29A12140DDF56E0A25894A40723D0AD7D97B2140DEF56E0A25894A40'::geography && _st_expand(geom, '0'::double precision)) AND _st_dwithin('0103000020E61000000100000005000000723D0AD7D97B2140DEF56E0A25894A40723D0AD7D97B21405FEC3BDDA78B4A40F7285C2F29A121405FEC3BDDA78B4A40F7285C2F29A12140DDF56E0A25894A40723D0AD7D97B2140DEF56E0A25894A40'::geography, geom, '0'::double precision, true))
               Rows Removed by Filter: 121
 Planning time: 0.967 ms
 Execution time: 3840.301 ms
(11 rows)



            QUERY PLAN
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 Nested Loop Left Join  (cost=2331.38..153199.05 rows=1 width=120) (actual time=0.553..115.846 rows=4766 loops=1)
   ->  Index Scan using idx_ops_planet_pois_geom on ops_planet_pois  (cost=0.42..8.81 rows=1 width=65) (actual time=0.366..31.569 rows=2807 loops=1)
         Index Cond: (geom && '0103000020E61000000100000005000000723D0AD7D97B2140DEF56E0A25894A40723D0AD7D97B21405FEC3BDDA78B4A40F7285C2F29A121405FEC3BDDA78B4A40F7285C2F29A12140DDF56E0A25894A40723D0AD7D97B2140DEF56E0A25894A40'::geography)
         Filter: (('0103000020E61000000100000005000000723D0AD7D97B2140DEF56E0A25894A40723D0AD7D97B21405FEC3BDDA78B4A40F7285C2F29A121405FEC3BDDA78B4A40F7285C2F29A12140DDF56E0A25894A40723D0AD7D97B2140DEF56E0A25894A40'::geography && _st_expand(geom, '0'::double precision)) AND _st_dwithin('0103000020E61000000100000005000000723D0AD7D97B2140DEF56E0A25894A40723D0AD7D97B21405FEC3BDDA78B4A40F7285C2F29A121405FEC3BDDA78B4A40F7285C2F29A12140DDF56E0A25894A40723D0AD7D97B2140DEF56E0A25894A40'::geography, geom, '0'::double precision, true))
         Rows Removed by Filter: 121
   ->  Bitmap Heap Scan on ops_planet_pois_tags  (cost=2330.96..152345.60 rows=84438 width=104) (actual time=0.017..0.017 rows=1 loops=2807)
         Recheck Cond: (ops_planet_pois.uuid = uuid)
         Heap Blocks: exact=1843
         ->  Bitmap Index Scan on ops_planet_pois_tags_uuid_idx  (cost=0.00..2309.85 rows=84438 width=0) (actual time=0.014..0.014 rows=1 loops=2807)
               Index Cond: (ops_planet_pois.uuid = uuid)
 Planning time: 1.157 ms
 Execution time: 116.145 ms
(12 rows)



SELECT * FROM ops_planet_pois p
INNER JOIN ops_planet_pois_tags t ON p.uuid=t.uuid
INNER JOIN ops_planet_pois_categories c ON p.uuid=c.uuid
WHERE p.uuid='\x5a90a66aaf1a47c4aa5b6466d67c65e4';



SELECT p.uuid, p.osm_id, array_agg(c.category), array_agg(t.key), array_agg(t.value) FROM ops_planet_pois p
INNER JOIN ops_planet_pois_tags t ON p.uuid=t.uuid
INNER JOIN ops_planet_pois_categories c ON p.uuid=c.uuid
GROUP BY p.uuid, p.osm_id;



WHERE p.uuid='\x5a90a66aaf1a47c4aa5b6466d67c65e4';




SELECT * FROM ops_planet_pois_categories WHERE uuid='\x5a90a66aaf1a47c4aa5b6466d67c65e4'




##### stats


SELECT anon_1.category,
Count(anon_1.category)
FROM (
     SELECT ops_planet_pois.uuid,
     ops_planet_pois_categories.category
     FROM ops_planet_pois
     LEFT OUTER JOIN ops_planet_pois_categories
     ON ops_planet_pois.uuid = ops_planet_pois_categories.uuid
     LEFT OUTER JOIN ops_planet_pois_tags
     ON ops_planet_pois.uuid = ops_planet_pois_tags.uuid
    WHERE st_dwithin(st_buffer(st_geogfromtext('POLYGON ((8.74189636230469 53.07144289415349, 8.814767341613772 53.07144289415349, 8.814767341613772 53.09106030870385, 8.74189636230469 53.09106030870385, 8.74189636230469 53.07144289415349))'), 0), ops_planet_pois.geom, 0)
    ) AS anon_1
GROUP BY anon_1.category;

SELECT Count(anon_1.category)
FROM (
     SELECT ops_planet_pois.uuid,
     ops_planet_pois_categories.category
     FROM ops_planet_pois
     LEFT OUTER JOIN ops_planet_pois_categories
     ON ops_planet_pois.uuid = ops_planet_pois_categories.uuid
    WHERE st_dwithin(st_buffer(st_geogfromtext('POLYGON ((8.74189636230469 53.07144289415349, 8.814767341613772 53.07144289415349, 8.814767341613772 53.09106030870385, 8.74189636230469 53.09106030870385, 8.74189636230469 53.07144289415349))'), 0), ops_planet_pois.geom, 0)
    ) AS anon_1


2738 vs 2764

