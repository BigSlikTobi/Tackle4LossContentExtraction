"""
Database access layer for article clustering operations.
"""

import uuid
import numpy as np
from supabase import create_client
from dotenv import load_dotenv
import os
import sys
import logging
from typing import Dict, List, Tuple, Optional

from core.clustering.vector_utils import parse_embedding

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Supabase client with proper error handling
def init_supabase_client() -> Optional[object]:
    """Initialize the Supabase client with proper error handling.
    
    Returns:
        Supabase client object or None if initialization fails
    """
    # Try loading from different possible .env locations
    for env_path in [
        None,  # Default location (current directory)
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),  # Project root
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'),  # Explicit .env file
    ]:
        try:
            if env_path:
                logger.info(f"Trying to load .env from: {env_path}")
                load_dotenv(dotenv_path=env_path)
            else:
                load_dotenv()
                
            SUPABASE_URL = os.getenv("SUPABASE_URL")
            SUPABASE_KEY = os.getenv("SUPABASE_KEY")
            
            if not SUPABASE_URL or not SUPABASE_KEY:
                logger.warning(f"Missing Supabase credentials when loading from {env_path or 'default location'}")
                continue
                
            logger.info(f"Found Supabase credentials, attempting connection")
            return create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {str(e)}")
            continue
    
    logger.error("Failed to initialize Supabase client with all attempted env locations")
    return None

# Try to initialize the Supabase client
sb = init_supabase_client()

if sb is None:
    logger.error("Could not initialize Supabase client. Please check your environment variables.")
    logger.error("Required environment variables: SUPABASE_URL, SUPABASE_KEY")
    logger.error("Make sure your .env file exists and contains these variables.")
    sys.exit(1)

def fetch_unclustered_articles() -> List[Tuple[int, np.ndarray]]:
    """Fetch articles without a cluster_id from the database.
    
    Returns:
        List of tuples with article ID and embedding vector
    """
    logger.info("Fetching unclustered articles...")
    resp = (
        sb.table("SourceArticles")
          .select("id, ArticleVector!inner(embedding)")
          .is_("cluster_id", None)
          .eq("contentType", "news_article")
          .order("created_at", desc=True)
          .limit(1000)
          .execute()
    )
    articles = []
    for r in resp.data:
        article_id = r["id"]
        if not r["ArticleVector"]:
            logger.warning(f"Article with ID {article_id} has an empty ArticleVector. Skipping.")
            continue
        emb_str = r["ArticleVector"][0]["embedding"]
        try:
            embedding_array = parse_embedding(emb_str)
            articles.append((article_id, embedding_array))
        except ValueError:
            logger.warning(f"Skipping article with ID {article_id} due to invalid embedding.")
    logger.info(f"Found {len(articles)} unclustered articles")
    return articles

def fetch_existing_clusters() -> List[Tuple[str, np.ndarray, int]]:
    """Fetch existing clusters with their centroids and counts.
    
    Returns:
        List of tuples with cluster ID, centroid vector, and member count
    """
    logger.info("Fetching existing clusters...")
    resp = sb.table("clusters")\
              .select("cluster_id, centroid, member_count")\
              .execute()
    
    clusters = []
    for r in resp.data:
        cluster_id = r["cluster_id"]
        member_count = r["member_count"]
        
        # Handle centroid whether it's a string or list
        centroid = r["centroid"]
        if isinstance(centroid, str):
            # Parse string representation of list
            centroid_values = [float(x) for x in centroid.strip('[]').split(',')]
            centroid_array = np.array(centroid_values, dtype=np.float32)
        else:
            # Already a list
            centroid_array = np.array(centroid, dtype=np.float32)
            
        clusters.append((cluster_id, centroid_array, member_count))
    
    logger.info(f"Found {len(clusters)} clusters")
    return clusters

def update_cluster_in_db(cluster_id: str, new_centroid: np.ndarray, new_count: int) -> None:
    """Update a cluster's centroid and member count in the database.
    
    Args:
        cluster_id: The ID of the cluster to update
        new_centroid: The updated centroid vector
        new_count: The updated member count
    """
    sb.table("clusters").update({
        "centroid": new_centroid.tolist(),
        "member_count": new_count,
        "updated_at": "now()"
    }).eq("cluster_id", cluster_id).execute()
    logger.debug(f"Updated cluster {cluster_id} in database (members: {new_count})")

def create_cluster_in_db(centroid: np.ndarray, member_count: int) -> str:
    """Create a new cluster in the database.
    
    Args:
        centroid: The centroid vector for the new cluster
        member_count: The initial member count
        
    Returns:
        The ID of the newly created cluster
    """
    cluster_id = str(uuid.uuid4())
    sb.table("clusters").insert({
        "cluster_id": cluster_id,
        "centroid": centroid.tolist(),
        "member_count": member_count
    }).execute()
    logger.info(f"Created new cluster {cluster_id} with {member_count} articles")
    return cluster_id

def assign_article_to_cluster(article_id: int, cluster_id: str) -> None:
    """Write the cluster_id back to the article record.
    
    Args:
        article_id: The ID of the article
        cluster_id: The ID of the cluster to assign the article to
    """
    sb.table("SourceArticles").update({
        "cluster_id": cluster_id
    }).eq("id", article_id).execute()
    logger.debug(f"Assigned article {article_id} to cluster {cluster_id}")