"""
Process module for clustering unclustered articles.

This process:
1. Fetches unclustered articles from the database
2. Fetches existing clusters
3. Tries to match articles to existing clusters
4. Creates new clusters from unmatched articles when possible
5. Updates the database with new cluster assignments
"""

import logging
import time
import os
import sys
from typing import Dict, List, Tuple

from Tackle4LossContentExtraction.core.clustering.db_access import (
    fetch_unclustered_articles,
    fetch_existing_clusters,
    batch_assign_articles_to_cluster
)
from Tackle4LossContentExtraction.core.clustering.cluster_manager import ClusterManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_clustering_process(similarity_threshold: float = 0.82, merge_threshold: float = 0.9) -> None:
    """
    Main entry point for the article clustering process.

    This function fetches unclustered articles and existing clusters, attempts to match articles to clusters,
    creates new clusters as needed, and updates the database with new assignments.

    Args:
        similarity_threshold (float): Minimum similarity score for articles to be considered related.
        merge_threshold (float): Threshold for merging similar clusters (should be higher than similarity_threshold).
    """
    process_start_time = time.time()
    logger.info(f"Starting article clustering process (threshold={similarity_threshold}, merge_threshold={merge_threshold})")
    
    # Initialize the cluster manager
    cluster_manager = ClusterManager(similarity_threshold)
    
    # Fetch unclustered articles and existing clusters
    unclustered_articles = fetch_unclustered_articles()
    cluster_manager.clusters = fetch_existing_clusters()
    
    if not unclustered_articles:
        logger.info("No unclustered articles found. Process complete.")
        return
    
    logger.info(f"Processing {len(unclustered_articles)} unclustered articles")

    assignments: List[Tuple[int, str]] = []

    # Process each article
    for article_id, article_vec in unclustered_articles:
        # Step 1: Try to match with existing clusters
        best_cluster = cluster_manager.find_best_cluster_match(article_vec)
        
        if best_cluster:
            # Found a matching cluster
            cluster_id, centroid, count, _ = best_cluster
            
            # Update the cluster with this article
            new_centroid, new_count = cluster_manager.update_cluster(
                cluster_id, centroid, count, article_vec
            )
            
            # Record the assignment for batch update
            assignments.append((article_id, cluster_id))
            
            # Update the in-memory cluster list
            cluster_manager.clusters = [
                (c_id, new_centroid, new_count) if c_id == cluster_id else (c_id, c, ct)
                for c_id, c, ct in cluster_manager.clusters
            ]
            continue
        
        # Step 2: Try to match with pending articles
        best_pending = cluster_manager.find_best_pending_match(article_vec)
        
        if best_pending:
            # Found a matching pending article
            pending_id, pending_vec, _ = best_pending
            
            # Create a new cluster with both articles
            cluster_id, new_centroid, new_count = cluster_manager.create_cluster(
                [pending_vec, article_vec]
            )
            
            # Record the assignments for batch update
            assignments.extend([
                (pending_id, cluster_id),
                (article_id, cluster_id)
            ])
            
            # Remove the pending article
            cluster_manager.remove_from_pending(pending_id)
            
            # Add the new cluster to the in-memory list
            cluster_manager.clusters.append((cluster_id, new_centroid, new_count))
            continue
        
        # Step 3: No match found, add to pending list
        cluster_manager.add_to_pending(article_id, article_vec)
    
    # Step 4: Check for and merge very similar clusters if we have enough clusters
    if len(cluster_manager.clusters) >= 2:
        logger.info("Checking for similar clusters to merge...")
        merged_count = 0
        while cluster_manager.check_and_merge_similar_clusters(merge_threshold):
            merged_count += 1
            # Limit the number of merge passes to avoid infinite loops
            if merged_count >= 10:
                logger.warning("Reached maximum merge iterations (10). Some clusters may still be mergeable.")
                break
        
        if merged_count > 0:
            logger.info(f"Completed {merged_count} cluster merge operations")
        else:
            logger.info("No clusters were similar enough to merge")
    
    if assignments:
        batch_assign_articles_to_cluster(assignments)

    process_end_time = time.time()
    logger.info(f"Clustering process completed in {process_end_time - process_start_time:.2f} seconds")
    logger.info(f"Processed {len(unclustered_articles)} articles, {len(cluster_manager.pending_articles)} remain pending")

if __name__ == "__main__":
    run_clustering_process()