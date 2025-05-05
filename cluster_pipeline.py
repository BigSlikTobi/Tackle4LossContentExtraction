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
from core.clustering.db_access import recalculate_cluster_member_counts

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def process_new(threshold: float = 0.82) -> None:
    """Run the article clustering process with the specified similarity threshold.
    
    This is a clean entry point without any business logic.
    All clustering functionality is delegated to the specialized modules.
    
    Args:
        threshold: Similarity threshold for cluster matching (default: 0.82)
    """
    logger.info(f"Starting article clustering workflow with threshold {threshold}")
    run_clustering_process(threshold)
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
