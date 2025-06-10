"""
Entry point for article clustering process.
This file has no business logic and acts as a clean workflow runner.
"""

import logging
import os
import sys

# Add root directory to Python path to allow importing core modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from modules.clustering.cluster_articles import run_clustering_process
from core.clustering.db_access import (
    recalculate_cluster_member_counts,
    update_old_clusters_status,
    repair_zero_centroid_clusters,
)

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

if __name__ == "__main__":
    process_new()
