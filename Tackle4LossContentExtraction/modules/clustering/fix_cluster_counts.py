#!/usr/bin/env python3
"""
Utility script to fix cluster member counts by recalculating based on actual article assignments.
This script also removes clusters with 0 or 1 members, as a proper cluster requires at least 2 articles.

Usage:
    python fix_cluster_counts.py
"""

import sys
import os
import logging

from Tackle4LossContentExtraction.core.clustering.db_access import recalculate_cluster_member_counts

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Run cluster member count fix process."""
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