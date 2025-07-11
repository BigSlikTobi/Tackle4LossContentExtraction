CREATE OR REPLACE FUNCTION recalculate_all_cluster_member_counts()
RETURNS JSON -- Returning JSON to allow for a structured success message or discrepancy details
LANGUAGE plpgsql
AS $$
DECLARE
    actual_counts RECORD;
    cluster_record RECORD;
    article_id_to_unassign INT;
    updated_cluster_ids UUID[];
    deleted_cluster_ids UUID[];
    unassigned_article_ids INT[];
    discrepancies JSONB := '{}'::JSONB; -- Initialize as empty JSONB object
BEGIN
    -- Step 1: Create a temporary table to store actual member counts
    CREATE TEMP TABLE temp_actual_counts AS
    SELECT
        c.cluster_id,
        COUNT(sa.id) AS actual_member_count,
        c.member_count AS old_member_count
    FROM
        clusters c
    LEFT JOIN
        SourceArticles sa ON c.cluster_id = sa.cluster_id
    GROUP BY
        c.cluster_id, c.member_count;

    -- Store discrepancies before updates
    FOR actual_counts IN SELECT * FROM temp_actual_counts LOOP
        IF actual_counts.actual_member_count <> actual_counts.old_member_count THEN
            discrepancies := jsonb_set(
                discrepancies,
                ARRAY[actual_counts.cluster_id::TEXT],
                jsonb_build_object('old', actual_counts.old_member_count, 'new', actual_counts.actual_member_count),
                TRUE
            );
        END IF;
    END LOOP;

    -- Step 2: Update clusters with 2 or more members if count is incorrect
    WITH updated_clusters AS (
        UPDATE
            clusters c
        SET
            member_count = tac.actual_member_count,
            updated_at = NOW(),
            status = CASE WHEN c.member_count <> tac.actual_member_count THEN 'UPDATED' ELSE c.status END
        FROM
            temp_actual_counts tac
        WHERE
            c.cluster_id = tac.cluster_id AND tac.actual_member_count >= 2 AND c.member_count <> tac.actual_member_count
        RETURNING c.cluster_id
    )
    SELECT array_agg(cluster_id) INTO updated_cluster_ids FROM updated_clusters;

    -- Step 3: Handle clusters with 1 member
    -- Unassign articles and collect cluster_ids for deletion
    CREATE TEMP TABLE temp_single_member_clusters_to_delete (cluster_id UUID, article_id INT);

    INSERT INTO temp_single_member_clusters_to_delete (cluster_id, article_id)
    SELECT tac.cluster_id, (SELECT sa.id FROM SourceArticles sa WHERE sa.cluster_id = tac.cluster_id LIMIT 1)
    FROM temp_actual_counts tac
    WHERE tac.actual_member_count = 1;

    WITH unassigned_articles AS (
        UPDATE SourceArticles sa
        SET cluster_id = NULL
        FROM temp_single_member_clusters_to_delete tsdc
        WHERE sa.id = tsdc.article_id
        RETURNING sa.id
    )
    SELECT array_agg(id) INTO unassigned_article_ids FROM unassigned_articles;

    -- Step 4: Delete clusters with 0 members or 1 member (after unassigning)
    WITH deleted_c AS (
        DELETE FROM clusters c
        WHERE EXISTS (
            SELECT 1 FROM temp_actual_counts tac
            WHERE tac.cluster_id = c.cluster_id AND tac.actual_member_count = 0
        ) OR EXISTS (
            SELECT 1 FROM temp_single_member_clusters_to_delete tsdc
            WHERE tsdc.cluster_id = c.cluster_id
        )
        RETURNING c.cluster_id
    )
    SELECT array_agg(cluster_id) INTO deleted_cluster_ids FROM deleted_c;

    -- Clean up temporary tables
    DROP TABLE temp_actual_counts;
    DROP TABLE temp_single_member_clusters_to_delete;

    RETURN json_build_object(
        'message', 'Cluster member counts recalculated successfully.',
        'updated_clusters', COALESCE(updated_cluster_ids, ARRAY[]::UUID[]),
        'deleted_clusters', COALESCE(deleted_cluster_ids, ARRAY[]::UUID[]),
        'unassigned_articles_from_single_member_clusters', COALESCE(unassigned_article_ids, ARRAY[]::INT[]),
        'discrepancies', discrepancies
    );

EXCEPTION
    WHEN OTHERS THEN
        -- Ensure temporary tables are dropped in case of an error
        DROP TABLE IF EXISTS temp_actual_counts;
        DROP TABLE IF EXISTS temp_single_member_clusters_to_delete;
        RAISE; -- Re-raise the exception
END;
$$;
