"""
CI-optimized entry point for article clustering process.
This version includes additional error handling and resource management
specifically designed for GitHub Actions CI environment.
"""

import logging
import os
import sys
import time
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

def process_new_ci(threshold: float = 0.82, merge_threshold: float = 0.9, max_retries: int = 3) -> None:
    """
    CI-optimized article clustering process with enhanced error handling.
    
    Args:
        threshold: Similarity threshold for cluster matching (default: 0.82)
        merge_threshold: Threshold for merging similar clusters (default: 0.9)
        max_retries: Maximum number of retry attempts for failed operations (default: 3)
    """
    if not acquire_lock():
        logger.info("Clustering pipeline is already running or lock file exists. Exiting.")
        sys.exit(0)
    
    try:
        logger.info("=== Starting CI-Optimized Clustering Pipeline ===")
        logger.info(f"Configuration: threshold={threshold}, merge_threshold={merge_threshold}, max_retries={max_retries}")
        
        # Step 1: Update old clusters with retry logic
        for attempt in range(max_retries):
            try:
                logger.info(f"Checking for clusters that need status update... (attempt {attempt + 1}/{max_retries})")
                old_clusters_count = update_old_clusters_status()
                if old_clusters_count > 0:
                    logger.info(f"Updated {old_clusters_count} clusters to 'OLD' status")
                break
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for old cluster status update: {e}")
                if attempt == max_retries - 1:
                    logger.error("Max retries reached for old cluster status update. Continuing...")
                else:
                    time.sleep(2 ** attempt)  # Exponential backoff

        # Step 2: Repair zero centroid clusters with retry logic
        for attempt in range(max_retries):
            try:
                logger.info(f"Repairing clusters with zero centroid... (attempt {attempt + 1}/{max_retries})")
                fixed = repair_zero_centroid_clusters()
                if fixed:
                    logger.info(f"Recalculated centroids for {len(fixed)} clusters")
                break
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for zero centroid repair: {e}")
                if attempt == max_retries - 1:
                    logger.error("Max retries reached for zero centroid repair. Continuing...")
                else:
                    time.sleep(2 ** attempt)  # Exponential backoff

        # Step 3: Run main clustering process with retry logic
        clustering_success = False
        for attempt in range(max_retries):
            try:
                logger.info(f"Starting main clustering process... (attempt {attempt + 1}/{max_retries})")
                logger.info(f"Using threshold {threshold} and merge threshold {merge_threshold}")
                run_clustering_process(threshold, merge_threshold)
                logger.info("Article clustering workflow completed successfully")
                clustering_success = True
                break
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed for main clustering: {e}")
                if attempt == max_retries - 1:
                    logger.error("Max retries reached for main clustering process. Pipeline failed.")
                    raise
                else:
                    time.sleep(5 * (attempt + 1))  # Longer backoff for main process

        # Step 4: Fix cluster member counts if main clustering succeeded
        if clustering_success:
            for attempt in range(max_retries):
                try:
                    logger.info(f"Verifying and fixing cluster member counts... (attempt {attempt + 1}/{max_retries})")
                    discrepancies = recalculate_cluster_member_counts()
                    if discrepancies:
                        logger.info(f"Fixed {len(discrepancies)} cluster member count discrepancies")
                    else:
                        logger.info("All cluster member counts are accurate")
                    break
                except Exception as e:
                    logger.warning(f"Attempt {attempt + 1} failed for member count verification: {e}")
                    if attempt == max_retries - 1:
                        logger.error("Max retries reached for member count verification. Continuing...")
                    else:
                        time.sleep(2 ** attempt)  # Exponential backoff

        logger.info("=== CI-Optimized Clustering Pipeline Complete ===")
        
    except Exception as e:
        logger.error(f"Critical error in clustering pipeline: {e}")
        raise
    finally:
        release_lock()
        logger.info("--- Clustering lock released. Pipeline shutdown complete. ---")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Run CI-optimized article clustering pipeline')
    parser.add_argument('--threshold', type=float, default=0.82,
                        help='Similarity threshold for cluster matching (default: 0.82)')
    parser.add_argument('--merge-threshold', type=float, default=0.9,
                        help='Threshold for merging similar clusters (default: 0.9)')
    parser.add_argument('--max-retries', type=int, default=3,
                        help='Maximum number of retry attempts (default: 3)')
    
    args = parser.parse_args()
    
    process_new_ci(
        threshold=args.threshold,
        merge_threshold=args.merge_threshold,
        max_retries=args.max_retries
    )
