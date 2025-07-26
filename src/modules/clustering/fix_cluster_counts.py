#!/usr/bin/env python3
"""
Utility script to fix cluster member counts by recalculating based on actual article assignments.
This script also removes clusters with 0 or 1 members, as a proper cluster requires at least 2 articles.
It ensures that the database reflects the correct number of articles in each cluster.

Process:
1. Fetch all clusters and their current member counts.
2. For each cluster, count the actual number of articles assigned to it.
3. If the count differs from the stored count, update the database.
4. Remove clusters with 0 or 1 members.
5. Unlink articles from single-member clusters.
6. Log the discrepancies and actions taken.
"""

import sys
import os
import logging

# Add root directory to Python path to allow importing core modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.clustering.db_access import recalculate_cluster_member_counts

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """
    Run cluster member count fix process.
    This function initializes the process to recalculate cluster member counts, checks for discrepancies, 
    and updates the database accordingly.
    Args:
        None
    Returns:
        None
    Raises:
        Exception: If there is an error during the recalculation or database update process.
    """
    logger.info("Starting to fix cluster member counts...")
    
    # Run the recalculation function
    discrepancies = recalculate_cluster_member_counts()
    
    # Report the results
    if discrepancies:
        logger.info(f"\nFixed {len(discrepancies)} cluster member count discrepancies:")
        logger.info("-" * 80)
        logger.info(f"{'Cluster ID':<40} {'Old Count':>8} {'New Count':>8} {'Difference':>10}")
        logger.info("-" * 80)
        
        for cluster_id, (old_count, new_count) in discrepancies.items():
            logger.info(f"{cluster_id:<40} {old_count:>8} {new_count:>8} {new_count - old_count:>+10}")
    else:
        logger.info("\nAll cluster member counts were already accurate.")
    
    # Check for zero/one member clusters in logs
    logger.info("\nProcess completed successfully.")
    logger.info("Note: Clusters with 0 or 1 members have been automatically removed,")
    logger.info("and articles from single-member clusters have been unlinked.")

if __name__ == "__main__":
    main()