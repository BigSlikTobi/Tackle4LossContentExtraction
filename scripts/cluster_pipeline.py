"""
Entry point for article clustering process.
This file has no business logic and acts as a clean workflow runner.
It imports the necessary modules and runs the clustering process.
It handles the lock management to ensure only one instance runs at a time.
The process flow is as follows:
1. Acquire a lock to prevent concurrent runs.
2. Check and update the status of old clusters. 
3. Repair any clusters with zero centroid.
4. Run the main clustering process with specified thresholds.
5. Recalculate cluster member counts to fix any discrepancies.
6. Release the lock after completion.
7. Log the process steps and outcomes.
"""

import logging
import os
import sys
from pathlib import Path

# Add src directory to Python path to allow importing project modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT / "src"))

# Import modules - check if we're in CI environment with PYTHONPATH set to root
if os.getenv('PYTHONPATH') == '.' or os.getenv('CI') == 'true':
    # In CI environment, imports are relative to project root
    from src.modules.clustering.cluster_articles import run_clustering_process
    from src.core.clustering.db_access import (
        recalculate_cluster_member_counts,
        update_old_clusters_status,
        repair_zero_centroid_clusters,
    )
    from src.core.utils.lock_manager import acquire_lock, release_lock
else:
    # In local environment, imports are relative to src directory
    try:
        from modules.clustering.cluster_articles import run_clustering_process
        from core.clustering.db_access import (
            recalculate_cluster_member_counts,
            update_old_clusters_status,
            repair_zero_centroid_clusters,
        )
        from core.utils.lock_manager import acquire_lock, release_lock
    except ImportError:
        # Fallback to src. prefix if relative imports fail
        from src.modules.clustering.cluster_articles import run_clustering_process
        from src.core.clustering.db_access import (
            recalculate_cluster_member_counts,
            update_old_clusters_status,
            repair_zero_centroid_clusters,
        )
        from src.core.utils.lock_manager import acquire_lock, release_lock

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
logger = logging.getLogger(__name__)

def process_new(threshold: float = 0.82, merge_threshold: float = 0.9) -> None:
    """Run the article clustering process with the specified similarity threshold.
    This is a clean entry point without any business logic.
    All clustering functionality is delegated to the specialized modules.
    Args:
        threshold: Similarity threshold for cluster matching (default: 0.82)
        merge_threshold: Threshold for merging similar clusters (default: 0.9)
    """
    if not acquire_lock():
        logger.info("Clustering pipeline is already running or lock file exists. Exiting.")
        sys.exit(0)
    
    try:
        # First, update status of old clusters (older than 5 days)
        logger.info("Checking for clusters that need status update...")
        old_clusters_count = update_old_clusters_status()
        if old_clusters_count > 0:
            logger.info(f"Updated {old_clusters_count} clusters to 'OLD' status")

        # Repair any clusters with zero centroid before clustering
        logger.info("Repairing clusters with zero centroid if needed...")
        fixed = repair_zero_centroid_clusters()
        if fixed:
            logger.info(f"Recalculated centroids for {len(fixed)} clusters")

        # Run the main clustering process
        logger.info(f"Starting article clustering workflow with threshold {threshold} and merge threshold {merge_threshold}")
        run_clustering_process(threshold, merge_threshold)
        logger.info("Article clustering workflow completed")

        # Automatically fix any cluster member count discrepancies
        logger.info("Verifying and fixing cluster member counts...")
        discrepancies = recalculate_cluster_member_counts()
        if discrepancies:
            logger.info(f"Fixed {len(discrepancies)} cluster member count discrepancies")
        else:
            logger.info("All cluster member counts are accurate")
    finally:
        release_lock()
        logger.info("--- Clustering lock released. Pipeline shutdown complete. ---")

if __name__ == "__main__":
    process_new()
