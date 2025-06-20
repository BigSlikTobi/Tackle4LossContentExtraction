# Acceptance Test: End-to-End Clustering Pipeline

## Objective
Verify that the clustering pipeline correctly processes new articles, clusters them, and updates their status in the database. This also includes the preliminary steps of content extraction and processing handled by the cleanup/processing pipeline which prepares articles for clustering.

## Preconditions
1. A test database is set up with a collection of unprocessed articles (e.g., `isProcessed=false`).
   - At least 3-4 articles with similar content that are expected to form a new cluster.
   - At least 2-3 articles with unique content that are expected to remain separate or form very small clusters.
   - (Optional) 1-2 existing clusters with a few articles, where one of the new unprocessed articles is highly similar to one of these existing clusters.
   - (Optional) Some clusters marked with 'UPDATED' status but old `updated_at` timestamps to test the 'OLD' status update logic.
2. The `Tackle4LossContentExtraction` package is notionally installed, and the environment is configured (e.g., `.env` file with API keys for Supabase and LLMs).

## Test Steps

### Part 1: Article Processing (Simulating `cleanup_pipeline.py` or `article_processor.py` behavior)
This part ensures articles are ready for clustering. In a real scenario, `cleanup_pipeline.py` would run. For this test, we assume equivalent processing occurs.

1. **Select Unprocessed Articles:** Identify a set of unprocessed articles in the test database matching the preconditions.
2. **Simulate Content Extraction & Cleaning:** For each selected article:
   - Assume `extract_main_content` is called.
   - Assume `extract_content_with_llm` and `analyze_content_type` are called.
3. **Simulate Embedding Creation & Storage:** For each successfully cleaned article with valid content:
   - Assume `create_and_store_embedding` is called.
4. **Simulate Database Update for Processed Articles:**
   - For each article, assume `update_article_in_db` is called to set `isProcessed=true`, `Content`, `contentType`, `Author`, etc.
   - **Expected State after Part 1:** The selected articles now have their `Content` field populated, `isProcessed` is true, `contentType` is determined, and a corresponding vector exists in `ArticleVector`.

### Part 2: Clustering Pipeline (Simulating `cluster_pipeline.py`)

5. **Run `cluster_pipeline.py`:**
   - Execute the main clustering script (e.g., `python -m Tackle4LossContentExtraction.cluster_pipeline`). This triggers `process_new()`.
6. **Verify Database State After Clustering:**
   - Query the `SourceArticles` table for the articles processed in Part 1.
   - Query the `clusters` table for new or updated clusters.
   - **Expected Database Changes:**
     - **Status Updates:** Old clusters (if any) should have their status updated to 'OLD' by `update_old_clusters_status`.
     - **Centroid Repairs:** Any zero-centroid clusters (if any intentionally set up) should be fixed by `repair_zero_centroid_clusters`.
     - **New Cluster Formation:** The 3-4 similar articles should now share the same `cluster_id`. A new entry in the `clusters` table should exist for this `cluster_id` with a `member_count` reflecting the number of articles.
     - **Existing Cluster Update:** If an unprocessed article was matched to an existing cluster, that cluster's `member_count` and `centroid` should be updated. The article gets the `cluster_id`.
     - **Separate Articles:** The 2-3 unique articles might either:
       - Remain unclustered (if no match and not enough similar pending articles).
       - Form very small new clusters (if they matched other pending articles not part of the main test set).
       - Be assigned to existing clusters if they unexpectedly matched.
     - **Cluster Member Counts:** `recalculate_cluster_member_counts` should ensure all `member_count` fields in the `clusters` table are accurate. Clusters with <2 members after this process are typically removed.
     - Articles that were successfully assigned to a cluster should have their `cluster_id` field populated.

## Success Criteria
- All logical steps of the pipeline (status updates, centroid repair, clustering, count recalculation) are executed (as would be shown by logs or mocked calls in a unit/integration test).
- Database state matches the expected outcomes after the simulated pipeline run.
  - Related articles are clustered together.
  - Unique articles are handled according to the defined logic (e.g., remain unclustered or form small clusters).
  - Cluster metadata (`member_count`, `centroid`, `status`) is consistent and correct.
- Log files (if applicable and captured) show the pipeline stages ran as expected without unexpected errors.

## Notes
- Due to current sandbox limitations (`ModuleNotFoundError`), direct execution of this test as a script is not feasible. This document outlines the intended test procedure and expected system behavior.
- For a fully automated acceptance test:
  - A dedicated test database with a well-defined initial state is essential.
  - Mocking of external services (LLM APIs) would be required to ensure deterministic behavior and avoid costs/rate limits.
  - Database assertions would be performed using direct DB queries or an ORM.
- This acceptance test focuses on data state changes and high-level flow. Lower-level unit and integration tests (like `test_integration_pipelines.py`) would cover specific function interactions and logic branches.
```
