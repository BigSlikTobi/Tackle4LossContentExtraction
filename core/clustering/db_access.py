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

from core.clustering.vector_utils import parse_embedding, normalize_vector_dimensions

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
    # sys.exit(1) # Allow sb to be None, tests will mock it, actual runs might raise errors later if sb is used while None.

class RPCCallFailedError(Exception):
    """Custom exception for RPC call failures."""
    pass

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

        centroid = r.get("centroid")
        if centroid is None:
            logger.warning(f"Skipping cluster {cluster_id} with NULL centroid")
            continue

        # Handle centroid whether it's a string or list
        if isinstance(centroid, str):
            centroid_values = [float(x) for x in centroid.strip('[]').split(',')]
            centroid_array = np.array(centroid_values, dtype=np.float32)
        else:
            centroid_array = np.array(centroid, dtype=np.float32)

        if centroid_array.ndim == 0:
            logger.warning(f"Skipping cluster {cluster_id} with invalid centroid shape")
            continue

        clusters.append((cluster_id, centroid_array, member_count))
    
    logger.info(f"Found {len(clusters)} clusters")
    return clusters

def update_cluster_in_db(cluster_id: str, new_centroid: np.ndarray, new_count: int, isContent: bool = False) -> None:
    """Update an existing cluster in the database.
    
    Args:
        cluster_id: The ID of the cluster to update
        new_centroid: The updated centroid vector
        new_count: The updated member count
        isContent: Whether the cluster has content associated with it
    """
    # Check if we need to normalize dimensions for the database
    # The database expects 768 dimensions, but our model might produce 1536
    if new_centroid.shape[0] != 768:
        template_vec = np.zeros(768)
        try:
            normalized_centroid, _ = normalize_vector_dimensions(new_centroid, template_vec)
            logger.info(f"Normalized centroid dimensions from {new_centroid.shape[0]} to {normalized_centroid.shape[0]}")
            new_centroid = normalized_centroid
        except ValueError as e:
            logger.error(f"Failed to normalize centroid dimensions: {e}")
            # If we can't normalize, just downsample to 768 dimensions
            if new_centroid.shape[0] > 768:
                step = new_centroid.shape[0] // 768
                new_centroid = new_centroid[::step][:768]
                logger.info(f"Downsampled centroid to 768 dimensions using step {step}")
    
    update_data = {
        "centroid": new_centroid.tolist(),
        "member_count": new_count,
        "updated_at": "now()",
        "status": "UPDATED",
        "isContent": isContent 
    }
    sb.table("clusters").update(update_data).eq("cluster_id", cluster_id).execute()
    logger.debug(f"Updated cluster {cluster_id} in database (members: {new_count}, isContent: {isContent})")

def create_cluster_in_db(centroid: np.ndarray, member_count: int) -> str:
    """Create a new cluster in the database.
    
    Args:
        centroid: The centroid vector for the new cluster
        member_count: The initial member count
        
    Returns:
        str: The ID of the newly created cluster
    """
    # Check if we need to normalize dimensions for the database
    # The database expects 768 dimensions, but our model might produce 1536
    if centroid.shape[0] != 768:
        template_vec = np.zeros(768)
        try:
            normalized_centroid, _ = normalize_vector_dimensions(centroid, template_vec)
            logger.info(f"Normalized centroid dimensions from {centroid.shape[0]} to {normalized_centroid.shape[0]}")
            centroid = normalized_centroid
        except ValueError as e:
            logger.error(f"Failed to normalize centroid dimensions: {e}")
            # If we can't normalize, just downsample to 768 dimensions
            if centroid.shape[0] > 768:
                step = centroid.shape[0] // 768
                centroid = centroid[::step][:768]
                logger.info(f"Downsampled centroid to 768 dimensions using step {step}")
    
    # Generate a new UUID for the cluster
    cluster_id = str(uuid.uuid4())
    sb.table("clusters").insert({
        "cluster_id": cluster_id,
        "centroid": centroid.tolist(),
        "member_count": member_count,
        "status": "NEW"
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

def batch_assign_articles_to_cluster(assignments: List[Tuple[int, str]]) -> None:
    """Assign multiple articles to clusters in a single database call.

    Args:
        assignments: A list of ``(article_id, cluster_id)`` tuples.
    """
    if not assignments:
        return
    update_rows = [
        {"id": aid, "cluster_id": cid} for aid, cid in assignments
    ]
    sb.table("SourceArticles").upsert(update_rows, on_conflict="id").execute()
    logger.debug(f"Batch assigned {len(assignments)} articles to clusters")

def repair_zero_centroid_clusters() -> List[str]:
    """Recalculate centroids for clusters where the stored centroid is all zeros.

    Returns a list of cluster IDs that were updated.
    """
    logger.info("Checking for clusters with zero centroid...")
    resp = sb.table("clusters").select("cluster_id, centroid").execute()

    fixed_clusters: List[str] = []

    for r in resp.data:
        centroid_raw = r.get("centroid")

        if centroid_raw is None:
            centroid_array = np.array([])
        elif isinstance(centroid_raw, str):
            values = [float(x) for x in centroid_raw.strip('[]').split(',')]
            centroid_array = np.array(values, dtype=np.float32)
        else:
            centroid_array = np.array(centroid_raw, dtype=np.float32)

        if (
            centroid_raw is None
            or centroid_array.ndim == 0
            or (centroid_array.ndim == 1 and np.allclose(centroid_array, 0))
        ):

            cluster_id = r["cluster_id"]
            articles_resp = (
                sb.table("SourceArticles")
                .select("id, ArticleVector!inner(embedding)")
                .eq("cluster_id", cluster_id)
                .execute()
            )

            embeddings: List[np.ndarray] = []
            for art in articles_resp.data:
                if not art.get("ArticleVector"):
                    continue
                emb_str = art["ArticleVector"][0]["embedding"]
                try:
                    embeddings.append(parse_embedding(emb_str))
                except ValueError:
                    logger.warning(
                        f"Skipping invalid embedding for article {art.get('id')} in cluster {cluster_id}"
                    )

            if embeddings:
                new_centroid = np.mean(np.vstack(embeddings), axis=0)
                update_cluster_in_db(cluster_id, new_centroid, len(embeddings), isContent=False)
                fixed_clusters.append(cluster_id)
                logger.info(f"Recalculated centroid for cluster {cluster_id}")
            else:
                logger.warning(
                    f"Cluster {cluster_id} has zero centroid but no valid embeddings were found"
                )

    if fixed_clusters:
        logger.info(f"Fixed centroids for {len(fixed_clusters)} clusters")
    else:
        logger.info("No zero centroid clusters found")

    return fixed_clusters

def recalculate_cluster_member_counts() -> Dict[str, Tuple[int, int]]:
    """
    Efficiently validates and corrects cluster member counts by calling a Supabase SQL function.

    The SQL function 'recalculate_all_cluster_member_counts' handles the core logic
    of counting members, updating/deleting clusters, and unassigning articles from
    single-member clusters atomically within the database.

    Returns:
        Dict[str, Tuple[int, int]]: A dictionary mapping cluster_id to a tuple of
                                     (old_count, new_count) for clusters where the
                                     count was changed. This is extracted from the
                                     'discrepancies' field in the JSON response
                                     from the SQL function.
    """
    logger.info("Calling RPC 'recalculate_all_cluster_member_counts' to fix cluster member counts...")

    if sb is None:
        logger.error("Supabase client 'sb' is not initialized. Cannot call RPC function.")
        raise RuntimeError("Supabase client not initialized.")

    try:
        response = sb.rpc('recalculate_all_cluster_member_counts').execute()
    except RPCCallFailedError as e: # Catch specific custom error
        logger.error(f"Error calling 'recalculate_all_cluster_member_counts' RPC: {str(e)}", exc_info=True)
        return {}
    # Let other unexpected Exceptions from the rpc call propagate for now to help debugging.

    # Process the response outside the RPC try-except if the call was successful
    if response and response.data: # Check response object itself too
        result_data = response.data # Supabase client typically puts JSON directly in .data
        logger.info(result_data.get('message', "Successfully recalculated cluster counts via RPC."))

        if result_data.get('updated_clusters'):
            logger.info(f"Clusters updated: {len(result_data['updated_clusters'])}")
        if result_data.get('deleted_clusters'):
            logger.info(f"Clusters deleted: {len(result_data['deleted_clusters'])}")
        if result_data.get('unassigned_articles_from_single_member_clusters'):
            logger.info(f"Articles unassigned from single-member clusters: {len(result_data['unassigned_articles_from_single_member_clusters'])}")

        # Extract discrepancies for the return value to maintain similar behavior for the caller
        # The SQL function returns discrepancies as a JSON object: {"cluster_id": {"old": X, "new": Y}, ...}
        raw_discrepancies = result_data.get('discrepancies', {})
        discrepancies_to_return = {}
        if isinstance(raw_discrepancies, dict):
            for cluster_id, counts in raw_discrepancies.items():
                if isinstance(counts, dict) and 'old' in counts and 'new' in counts:
                    discrepancies_to_return[cluster_id] = (counts['old'], counts['new'])
                else:
                    logger.warning(f"Unexpected format for discrepancy item: {cluster_id} -> {counts}")

        if discrepancies_to_return:
            logger.info(f"Found {len(discrepancies_to_return)} cluster member count discrepancies through RPC.")
        else:
            logger.info("No cluster member count discrepancies reported by RPC.")

        return discrepancies_to_return
    else:
        # This case handles if response is None or response.data is None/empty
        # The supabase-py client might raise PostgrestAPIError for HTTP errors,
        # which would be caught by the try-except block above.
        # This 'else' handles unexpected non-error empty responses from the RPC call.
        logger.error("No data returned from 'recalculate_all_cluster_member_counts' RPC call or response.data is empty, and no exception was raised during the call.")
        return {}

def update_old_clusters_status() -> int:
    """Update status of clusters to 'OLD' if they haven't been updated in 3 days.
    
    Returns:
        Number of clusters updated to OLD status
    """
    logger.info("Checking for clusters that haven't been updated in 3 days...")
    
    # Fetch clusters that aren't already marked as OLD
    resp = sb.table("clusters")\
             .select("cluster_id, updated_at")\
             .not_.eq("status", "OLD")\
             .execute()
    
    # In Python, calculate which clusters are older than 3 days
    from datetime import datetime, timedelta
    
    three_days_ago = datetime.now() - timedelta(days=3)
    old_cluster_ids = []
    
    for cluster in resp.data:
        if "updated_at" in cluster and cluster["updated_at"]:
            # Parse the timestamp from the database
            updated_at = datetime.fromisoformat(cluster["updated_at"].replace("Z", "+00:00"))
            
            # Check if it's older than 3 days
            if updated_at < three_days_ago:
                old_cluster_ids.append(cluster["cluster_id"])
    
    # If we found old clusters, update their status
    num_updated = 0
    if old_cluster_ids:
        for cluster_id in old_cluster_ids:
            update_resp = sb.table("clusters")\
                            .update({"status": "OLD"})\
                            .eq("cluster_id", cluster_id)\
                            .execute()
            num_updated += 1
    
    if num_updated > 0:
        logger.info(f"Updated {num_updated} clusters to 'OLD' status")
    else:
        logger.debug("No clusters needed to be updated to 'OLD' status")
    
    return num_updated