"""
Business logic for article clustering.
This module manages the clustering process, including updating cluster statuses,
creating new clusters, and finding matches for articles.
It handles the core logic for clustering articles based on their content vectors,
and interacts with the database to manage cluster data.
It also includes methods for updating cluster member counts and merging similar clusters.
This module is designed to be used by the clustering pipeline and does not contain any
business logic outside of clustering operations.
It is intended to be used in conjunction with the `cluster_pipeline.py` script,
which orchestrates the overall clustering workflow and not as a standalone script.
"""

import numpy as np
import logging
from typing import Dict, List, Tuple, Optional

from src.core.clustering.vector_utils import cosine_similarity, normalize_vector_dimensions
from src.core.clustering.db_access import (
    update_cluster_in_db,
    create_cluster_in_db,
    batch_assign_articles_to_cluster
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ClusterManager:
    """
    Manager class for handling article clustering operations.

    Attributes:
        similarity_threshold (float): Minimum similarity score for articles to be considered related.
        pending_articles (Dict[int, np.ndarray]): Articles not yet assigned to a cluster.
        clusters (List[Tuple[str, np.ndarray, int]]): List of clusters as (cluster_id, centroid, member_count).
    """
    def __init__(self, similarity_threshold: float = 0.82, check_old_clusters: bool = True):
        """
        Initialize the ClusterManager.
        This sets up the similarity threshold and initializes the pending articles and clusters.
        Args:
            similarity_threshold (float): Minimum similarity score for articles to be considered related.
            check_old_clusters (bool): Whether to check and update status of old clusters during initialization.
        Returns:
            None
        Raises:
            ValueError: If similarity_threshold is not between 0 and 1.
        """
        self.similarity_threshold = similarity_threshold
        self.pending_articles: Dict[int, np.ndarray] = {}
        self.clusters: List[Tuple[str, np.ndarray, int]] = []
        # Check and update cluster statuses if enabled
        if check_old_clusters:
            from src.core.clustering.db_access import update_old_clusters_status
            update_old_clusters_status()

    def update_cluster(self, cluster_id: str, old_centroid: np.ndarray, 
                      old_count: int, new_vector: np.ndarray) -> Tuple[np.ndarray, int]:
        """
        Update a cluster with a new article vector.
        This recalculates the centroid and member count of the cluster.
        Args:
            cluster_id (str): The ID of the cluster to update.
            old_centroid (np.ndarray): The current centroid of the cluster.
            old_count (int): The current member count of the cluster.
            new_vector (np.ndarray): The vector of the article to add to the cluster.
        Returns:
            Tuple[np.ndarray, int]: The new centroid and the updated member count.
        Raises:
            ValueError: If the cluster member count is less than 2.
        """
        if old_count < 2:
            raise ValueError("Cluster member count must be at least 2")
        # Handle dimension mismatch
        old_centroid, new_vector = normalize_vector_dimensions(old_centroid, new_vector)
        # Calculate new centroid
        new_centroid = (old_centroid * old_count + new_vector) / (old_count + 1)
        new_count = old_count + 1
        # Update the cluster in the database, setting isContent to False
        update_cluster_in_db(cluster_id, new_centroid, new_count, isContent=False)
        logger.debug(f"Updated cluster {cluster_id} (members {old_count} -> {new_count})")
        return new_centroid, new_count

    def create_cluster(self, vectors: List[np.ndarray]) -> Tuple[str, np.ndarray, int]:
        """
        Create a new cluster from a list of vectors.
        This calculates the centroid of the provided vectors and creates a new cluster in the database.
        Args:
            vectors (List[np.ndarray]): List of article vectors to form a cluster.
        Returns:
            Tuple[str, np.ndarray, int]: The cluster ID, centroid, and member count.
        Raises:
            ValueError: If no vectors are provided.
        """
        if not vectors:
            raise ValueError("Cannot create a cluster with no vectors")
        # Stack vectors and calculate mean
        centroid = np.mean(np.vstack(vectors), axis=0)
        
        # Dimension normalization will now be handled in create_cluster_in_db
        # No need to manually downsample here, keeping the full dimensions for accuracy
        
        # Create the cluster in the database
        cluster_id = create_cluster_in_db(centroid, len(vectors))
        return cluster_id, centroid, len(vectors)

    def find_best_cluster_match(self, 
                                article_vec: np.ndarray) -> Optional[Tuple[str, np.ndarray, int, float]]:
        """
        Find the best matching cluster for an article vector.
        This compares the article vector against existing clusters and returns the best match above the similarity threshold.
        If no suitable match is found, it returns None.
        Args:
            article_vec (np.ndarray): The vector of the article to match.
        Returns:
            Optional[Tuple[str, np.ndarray, int, float]]: Tuple with cluster ID, centroid, count, and similarity score if a match is found, or None if no suitable match is found.
        """
        best_score = self.similarity_threshold
        best_match = None
        for cluster_id, centroid, count in self.clusters:
            score = cosine_similarity(article_vec, centroid)
            if score > best_score:
                best_score = score
                best_match = (cluster_id, centroid, count, score)
                
        # Changed from breaking at first successful match to evaluating all clusters
        # and returning the best matching one above the threshold
        return best_match

    def find_best_pending_match(self, 
                               article_vec: np.ndarray) -> Optional[Tuple[int, np.ndarray, float]]:
        """
        Find the best matching pending article.
        This compares the article vector against pending articles and returns the best match above the similarity threshold.
        If no suitable match is found, it returns None.
        Args:
            article_vec (np.ndarray): The vector of the article to match.
        Returns:
            Optional[Tuple[int, np.ndarray, float]]: Tuple with article ID, vector, and similarity score if a match is found, or None if no suitable match is found.
        """
        best_score = self.similarity_threshold
        best_match = None
        for article_id, vector in self.pending_articles.items():
            score = cosine_similarity(article_vec, vector)
            if score > best_score:
                best_score = score
                best_match = (article_id, vector, score)
        return best_match

    def add_to_pending(self, article_id: int, vector: np.ndarray) -> None:
        """
        Add an article to the pending list.
        This stores articles that are not yet assigned to any cluster.
        This is useful for articles that are still being processed or need to be clustered later.
        Args:
            article_id (int): ID of the article to add.
            vector (np.ndarray): The vector of the article.
        Returns:
            None
        Raises:
            ValueError: If the vector is not a valid numpy array.
        """
        self.pending_articles[article_id] = vector
        logger.debug(f"Added article {article_id} to pending list")

    def remove_from_pending(self, article_id: int) -> None:
        """
        Remove an article from the pending list.
        This is used when an article has been successfully clustered or processed.
        It ensures that the pending articles list is kept up-to-date.   
        Args:
            article_id (int): ID of the article to remove.
        Returns:
            None
        Raises:
            KeyError: If the article ID is not found in the pending list.
        """
        if article_id in self.pending_articles:
            del self.pending_articles[article_id]
            logger.debug(f"Removed article {article_id} from pending list")

    def update_cluster_statuses(self) -> int:
        """
        Update the statuses of clusters based on their age.
        This method marks clusters as 'OLD' if they haven't been updated in 5 days and aren't already marked as 'OLD'.
        It returns the number of clusters that were updated.
        Args:
            None    
        Returns:
            int: Number of clusters updated to 'OLD' status.
        Raises:
            Exception: If there is an error updating the cluster statuses in the database.
        """
        from src.core.clustering.db_access import update_old_clusters_status
        return update_old_clusters_status()

    def check_and_merge_similar_clusters(self, merge_threshold: float = 0.9) -> bool:
        """
        Check if there are any highly similar clusters that should be merged.
        This method compares all pairs of clusters and merges them if their centroids are very similar. 
        Args:
            merge_threshold (float): Minimum similarity score for clusters to be considered for merging.
                                   Should be higher than the regular similarity_threshold. 
        Returns:
            bool: True if any clusters were merged, False otherwise.
        Raises:
            ValueError: If merge_threshold is not between 0 and 1.
        """
        if len(self.clusters) < 2:
            logger.debug("Not enough clusters to consider merging.")
            return False
            
        merged = False
        # Make a copy to avoid modifying during iteration
        clusters_to_check = list(self.clusters)
        
        for i, (cluster_id1, centroid1, count1) in enumerate(clusters_to_check):
            for j, (cluster_id2, centroid2, count2) in enumerate(clusters_to_check[i+1:], i+1):
                try:
                    # Compute similarity between cluster centroids
                    similarity = cosine_similarity(centroid1, centroid2)
                    
                    if similarity > merge_threshold:
                        logger.info(f"Found similar clusters to merge: {cluster_id1} and {cluster_id2} with similarity {similarity:.4f}")
                        
                        # Merge the smaller cluster into the larger one for stability
                        if count1 >= count2:
                            primary_id, primary_centroid, primary_count = cluster_id1, centroid1, count1

                            secondary_id, secondary_centroid, secondary_count = cluster_id2, centroid2, count2
                        else:
                            primary_id, primary_centroid, primary_count = cluster_id2, centroid2, count2
                            secondary_id, secondary_centroid, secondary_count = cluster_id1, centroid1, count1
                        
                        # Calculate weighted average of centroids
                        total_count = primary_count + secondary_count
                        new_centroid = ((primary_centroid * primary_count) + (secondary_centroid * secondary_count)) / total_count
                        
                        # Update the primary cluster in the database
                        update_cluster_in_db(primary_id, new_centroid, total_count, isContent=False)
                        
                        # Reassign articles from secondary cluster to primary cluster in batch
                        from src.core.clustering.db_access import sb
                        articles_resp = sb.table("SourceArticles").select("id").eq("cluster_id", secondary_id).execute()
                        sec_ids = [a["id"] for a in articles_resp.data]
                        batch_assign_articles_to_cluster([(aid, primary_id) for aid in sec_ids])
                        
                        # Delete the secondary cluster from the database
                        sb.table("clusters").delete().eq("cluster_id", secondary_id).execute()
                        
                        # Update the in-memory clusters list
                        self.clusters = [(id, centroid, count) for id, centroid, count in self.clusters 
                                        if id != secondary_id]
                        
                        # Update the primary cluster in the in-memory list
                        self.clusters = [(primary_id if id == primary_id else id, 
                                       new_centroid if id == primary_id else centroid,
                                       total_count if id == primary_id else count)
                                      for id, centroid, count in self.clusters]
                        
                        merged = True
                        logger.info(f"Merged cluster {secondary_id} into {primary_id}. New count: {total_count}")
                        
                        # Since we modified the clusters list, break out and restart if needed
                        break
                    
                except Exception as e:
                    logger.error(f"Error comparing clusters {cluster_id1} and {cluster_id2}: {str(e)}")
                
            if merged:
                break
                
        return merged