# Acceptance Test Plan for `fix_cluster_counts.py`

This document outlines the acceptance testing strategy for verifying the `fix_cluster_counts.py` script, particularly after its modification to use an efficient database-side SQL function for recalculating cluster member counts.

## 1. Manual Acceptance Test Scenario

**Objective:** Verify that the `fix_cluster_counts.py` script correctly updates cluster member counts, handles empty and single-member clusters, and appears to complete without errors using the new database-driven logic.

**Prerequisites:**
*   A working Supabase instance with the schema (`clusters`, `SourceArticles` tables) and the `recalculate_all_cluster_member_counts` SQL function deployed.
*   Supabase URL and Key configured in the environment (e.g., via a `.env` file) for `core/clustering/db_access.py`.
*   The codebase checked out to the version containing the new changes.
*   Python environment with necessary dependencies (`supabase-py`, `python-dotenv`, `numpy`).

**Test Steps:**

*   **Step 1: Prepare Initial Data State (Database)**
    *   Connect to your Supabase database.
    *   **Scenario A (Incorrect Counts):**
        *   Create a cluster (e.g., `cluster_A_manual`) with `member_count = 10` in the `clusters` table.
        *   In `SourceArticles`, assign only 3 articles to `cluster_A_manual`.
    *   **Scenario B (Empty Cluster):**
        *   Create a cluster (e.g., `cluster_B_manual`) with `member_count = 5` in the `clusters` table.
        *   Ensure no articles in `SourceArticles` are assigned to `cluster_B_manual`.
    *   **Scenario C (Single-Member Cluster):**
        *   Create a cluster (e.g., `cluster_C_manual`) with `member_count = 1` (or >1, e.g., 3) in the `clusters` table.
        *   In `SourceArticles`, assign exactly 1 article (e.g., `article_X_manual`) to `cluster_C_manual`.
    *   **Scenario D (Correct Count):**
        *   Create a cluster (e.g., `cluster_D_manual`) with `member_count = 2` in the `clusters` table.
        *   In `SourceArticles`, assign 2 articles to `cluster_D_manual`.
    *   Record the IDs of these clusters and articles.

*   **Step 2: Run the Script**
    *   Open a terminal in the project's root directory.
    *   Execute the script: `python modules/clustering/fix_cluster_counts.py`

*   **Step 3: Observe Script Output**
    *   The script should log messages indicating it's starting, calling the recalculation logic, and reporting results.
    *   Look for logs from `core.clustering.db_access.recalculate_cluster_member_counts` indicating the RPC call was made.
    *   The script should report the discrepancies found and fixed. For `cluster_A_manual`, it should show old count 10, new count 3. For `cluster_B_manual`, old count 5, new count 0. For `cluster_C_manual`, old count (e.g., 3), new count 1.
    *   It should log information about deleted clusters and unassigned articles if the RPC call returns that.

*   **Step 4: Verify Data State (Database)**
    *   Connect to the Supabase database again.
    *   **Scenario A:** Query `cluster_A_manual`. Its `member_count` should now be 3.
    *   **Scenario B:** Query `cluster_B_manual`. It should no longer exist (deleted).
    *   **Scenario C:** Query `cluster_C_manual`. It should no longer exist. Query `article_X_manual`. Its `cluster_id` should now be `NULL`.
    *   **Scenario D:** Query `cluster_D_manual`. Its `member_count` should still be 2.

*   **Step 5: (Qualitative) Assess Performance/Atomicity**
    *   Observe if the script completes in a reasonable time for the small dataset.
    *   The expectation is that the database function handles changes atomically. (This is hard to verify manually without specific tooling).

**Expected Results:**
*   All cluster counts are corrected in the database.
*   Empty clusters are deleted.
*   Single-member clusters are deleted, and their articles are unassigned.
*   The script runs without error and provides informative logs.
*   The process relies on a single RPC call to the database function.

## 2. Considerations for a Scripted Acceptance Test

If a more automated acceptance test were to be built, it would script the "Manual Acceptance Test Scenario":

*   **Test Framework:** Use a Python test framework like `pytest` or `unittest`.
*   **Database Interaction:** Programmatically set up database state before tests and query after to verify.
*   **Script Execution:** Use Python's `subprocess` module to run `modules/clustering/fix_cluster_counts.py`.
*   **Assertions:** Assert on script's exit code, log messages, and final database state.
*   **Race Condition/Concurrency (Advanced):** Testing for improved atomicity would be complex and might involve a test harness to simulate concurrent writes while the script runs. This is generally out of scope for typical acceptance tests unless specifically required and resourced.
