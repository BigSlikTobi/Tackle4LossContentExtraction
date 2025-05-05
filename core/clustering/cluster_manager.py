"""
Business logic for article clustering.
"""

import numpy as np
import logging
from typing import Dict, List, Tuple, Optional

from core.clustering.vector_utils import cosine_similarity, normalize_vector_dimensions
from core.clustering.db_access import (
    update_cluster_in_db, 
    create_cluster_in_db, 
    assign_article_to_cluster
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ClusterManager:
    """Manager class for handling article clustering operations."""
    
    def __init__(self, similarity_threshold: float = 0.82, check_old_clusters: bool = True):
        """Initialize the ClusterManager.
        
        Args:
            similarity_threshold: Minimum similarity score for articles to be considered related
            check_old_clusters: Whether to check and update status of old clusters during initialization
        """
        self.similarity_threshold = similarity_threshold
        self.pending_articles: Dict[int, np.ndarray] = {}
        self.clusters: List[Tuple[str, np.ndarray, int]] = []
        
        # Check and update cluster statuses if enabled
        if check_old_clusters:
            from core.clustering.db_access import update_old_clusters_status
            update_old_clusters_status()
        
    def update_cluster(self, cluster_id: str, old_centroid: np.ndarray, 
                      old_count: int, new_vector: np.ndarray) -> Tuple[np.ndarray, int]:
        """Update a cluster with a new article vector.
        
        Args:
            cluster_id: The ID of the cluster to update
            old_centroid: The current centroid of the cluster
            old_count: The current member count of the cluster
            new_vector: The vector of the article to add to the cluster
            
        Returns:
            Tuple containing the new centroid and the updated member count
        """
        if old_count < 2:
            raise ValueError("Cluster member count must be at least 2")
        
        # Handle dimension mismatch
        old_centroid, new_vector = normalize_vector_dimensions(old_centroid, new_vector)
        
        # Calculate new centroid
        new_centroid = (old_centroid * old_count + new_vector) / (old_count + 1)
        new_count = old_count + 1
        
        # Update the cluster in the database
        update_cluster_in_db(cluster_id, new_centroid, new_count)
        
        logger.debug(f"Updated cluster {cluster_id} (members {old_count} -> {new_count})")
        return new_centroid, new_count
    
    def create_cluster(self, vectors: List[np.ndarray]) -> Tuple[str, np.ndarray, int]:
        """Create a new cluster from a list of vectors.
        
        Args:
            vectors: List of article vectors to form a cluster
            
        Returns:
            Tuple containing the cluster ID, centroid, and member count
        """
        if not vectors:
            raise ValueError("Cannot create a cluster with no vectors")
            
        # Stack vectors and calculate mean
        centroid = np.mean(np.vstack(vectors), axis=0)
        
        # Downsample if 1536 -> 768 dims (common when dealing with different embedding models)
        if centroid.shape[0] == 1536:
            centroid = centroid[::2]
            
        # Create the cluster in the database
        cluster_id = create_cluster_in_db(centroid, len(vectors))
        
        return cluster_id, centroid, len(vectors)
    
    def find_best_cluster_match(self, 
                               article_vec: np.ndarray) -> Optional[Tuple[str, np.ndarray, int, float]]:
        """Find the best matching cluster for an article vector.
        
        Args:
            article_vec: The vector of the article to match
            
        Returns:
            Tuple with cluster ID, centroid, count, and similarity score if a match is found,
            or None if no suitable match is found
        """
        best_score = self.similarity_threshold
        best_match = None
        
        for cluster_id, centroid, count in self.clusters:
            score = cosine_similarity(article_vec, centroid)
            if score > best_score:
                best_score = score
                best_match = (cluster_id, centroid, count, score)
                
        return best_match
    
    def find_best_pending_match(self, 
                               article_vec: np.ndarray) -> Optional[Tuple[int, np.ndarray, float]]:
        """Find the best matching pending article.
        
        Args:
            article_vec: The vector of the article to match
            
        Returns:
            Tuple with article ID, vector, and similarity score if a match is found,
            or None if no suitable match is found
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
        """Add an article to the pending list.
        
        Args:
            article_id: ID of the article to add
            vector: The vector of the article
        """
        self.pending_articles[article_id] = vector
        logger.debug(f"Added article {article_id} to pending list")
    
    def remove_from_pending(self, article_id: int) -> None:
        """Remove an article from the pending list.
        
        Args:
            article_id: ID of the article to remove
        """
        if article_id in self.pending_articles:
            del self.pending_articles[article_id]
            logger.debug(f"Removed article {article_id} from pending list")
    
    def update_cluster_statuses(self) -> int:
        """Update the statuses of clusters based on their age.
        
        This method marks clusters as 'OLD' if they haven't been updated in 5 days
        and aren't already marked as 'OLD'.
        
        Returns:
            Number of clusters updated to 'OLD' status
        """
        from core.clustering.db_access import update_old_clusters_status
        return update_old_clusters_status()