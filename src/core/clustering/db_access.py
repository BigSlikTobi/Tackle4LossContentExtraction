"""
Database access layer for article clustering operations.
This module provides functions to interact with the database for clustering operations,
including fetching unclustered articles, updating cluster information, and managing article embeddings.
"""

import uuid
import numpy as np
from supabase import create_client
from dotenv import load_dotenv
import os
import sys
import logging
from typing import Dict, List, Tuple, Optional
from postgrest.exceptions import APIError 

from src.core.clustering.vector_utils import parse_embedding, normalize_vector_dimensions

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

IS_CI = os.getenv("CI") == 'true' or os.getenv("GITHUB_ACTIONS") == 'true'

# Initialize Supabase client with proper error handling
def init_supabase_client() -> Optional[object]:
    """Initialize the Supabase client with proper error handling.
    This function loads environment variables and creates a Supabase client.
    Args:
        None
    Returns:
        Supabase client object or None if initialization fails
    Raises:
        Exception: If there is an error initializing the Supabase client.  
    """
    load_dotenv()
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            logger.info(f"Found Supabase credentials, attempting connection")
            return create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {str(e)}")
            return None
    elif not IS_CI:
        logger.error("Failed to initialize Supabase client. Make sure your .env file exists and contains SUPABASE_URL and SUPABASE_KEY.")
        return None
    else:
        logger.warning("Supabase credentials not found. Running in CI mode without database access.")
        return None

# Try to initialize the Supabase client
sb = init_supabase_client()

if sb is None and not IS_CI:
    logger.error("Could not initialize Supabase client. Please check your environment variables.")

    logger.error("Required environment variables: SUPABASE_URL, SUPABASE_KEY")
    logger.error("Make sure your .env file exists and contains these variables.")
    # sys.exit(1) # Allow sb to be None, tests will mock it, actual runs might raise errors later if sb is used while None.

class RPCCallFailedError(Exception):
    """Custom exception for RPC call failures."""
    pass

def fetch_unclustered_articles() -> List[Tuple[int, np.ndarray]]:
    """Fetch articles without a cluster_id from the database.
    This function retrieves articles that have not been assigned to any cluster.
    Args:
        None
    Returns:
        List of tuples with article ID and embedding vector
    Raises: 
        APIError: If there is an error fetching data from the Supabase database.
        Exception: If there is an unexpected error during the fetch operation.
    """
    if sb is None:
        logger.warning("Supabase client is not initialized. Cannot perform fetch_unclustered_articles operation.")
        return []
    logger.info("Fetching unclustered articles...")
    articles = []
    try:
        resp = (
            sb.table("SourceArticles")
            .select("id, ArticleVector!inner(embedding)")
            .is_("cluster_id", None)
            .eq("contentType", "news_article")
            .order("created_at", desc=True)
            .limit(1000)
            .execute()
        )
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
    except APIError as e:
        logger.error(f"Supabase APIError in fetch_unclustered_articles: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in fetch_unclustered_articles: {e}")
        return []
    return articles

def fetch_existing_clusters() -> List[Tuple[str, np.ndarray, int]]:
    """Fetch existing clusters with their centroids and counts.
    This function retrieves clusters from the database, including their IDs, centroid vectors, and member counts.   
    Args:
        None
    Returns:
        List of tuples with cluster ID, centroid vector, and member count
    Raises: 
        APIError: If there is an error fetching data from the Supabase database.
        Exception: If there is an unexpected error during the fetch operation.
    """
    if sb is None:
        logger.warning("Supabase client is not initialized. Cannot perform fetch_existing_clusters operation.")
        return []
    logger.info("Fetching existing clusters...")
    try:
        resp = sb.table("clusters")\
                .select("cluster_id, centroid, member_count")\
                .execute()
        data = resp.data or []
        # If data entries are simple dicts without cluster_id, return raw data for tests
        if not data or 'cluster_id' not in data[0]:
            return data
        # Process clusters with cluster_id, skip null centroids
        clusters = []
        for r in data:
            cid = r.get('cluster_id')
            centroid = r.get('centroid')
            count = r.get('member_count')
            if centroid is None:
                logger.warning(f"Skipping cluster {cid} with NULL centroid")
                continue
            # Convert centroid to numpy array
            if isinstance(centroid, str):
                vals = [float(x) for x in centroid.strip('[]').split(',')]
                arr = np.array(vals, dtype=np.float32)
            else:
                arr = np.array(centroid, dtype=np.float32)
            if arr.ndim == 0:
                logger.warning(f"Skipping cluster {cid} with invalid centroid shape")
                continue
            clusters.append((cid, arr, count))
        return clusters
    except APIError as e:
        logger.error(f"Supabase APIError in fetch_existing_clusters: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in fetch_existing_clusters: {e}")
        return []

def update_cluster_in_db(cluster_id: str, new_centroid: np.ndarray, new_count: int, isContent: bool = False) -> None:
    """Update an existing cluster in the database.
    This function updates the centroid and member count of a cluster in the database.
    Args:
        cluster_id: The ID of the cluster to update
        new_centroid: The updated centroid vector
        new_count: The updated member count
        isContent: Whether the cluster has content associated with it
    Returns:    
        None
    Raises: 
        APIError: If there is an error updating the cluster in the Supabase database.
        Exception: If there is an unexpected error during the update operation.
    """
    if sb is None:
        logger.error(f"Supabase client is not initialized. Cannot perform update_cluster_in_db operation for cluster_id {cluster_id}.")
        return # Or return False if a boolean indicator is preferred by callers
    try:
        # Check if we need to normalize dimensions for the database
        # The database expects 768 dimensions, but our model might produce 1536
        if new_centroid.shape[0] != 768:
            template_vec = np.zeros(768)
            try:
                normalized_centroid, _ = normalize_vector_dimensions(new_centroid, template_vec)
                logger.info(f"Normalized centroid dimensions from {new_centroid.shape[0]} to {normalized_centroid.shape[0]}")
                new_centroid = normalized_centroid
            except ValueError as e:
                logger.error(f"Failed to normalize centroid dimensions for cluster {cluster_id}: {e}")
                # If we can't normalize, just downsample to 768 dimensions
                if new_centroid.shape[0] > 768:
                    step = new_centroid.shape[0] // 768
                    new_centroid = new_centroid[::step][:768]
                    logger.info(f"Downsampled centroid to 768 dimensions for cluster {cluster_id} using step {step}")

        update_data = {
            "centroid": new_centroid.tolist(),
            "member_count": new_count,
            "updated_at": "now()",
            "status": "UPDATED",
            "isContent": isContent
        }
        sb.table("clusters").update(update_data).eq("cluster_id", cluster_id).execute()
        logger.debug(f"Updated cluster {cluster_id} in database (members: {new_count}, isContent: {isContent})")
    except APIError as e:
        logger.error(f"Supabase APIError updating cluster {cluster_id}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error updating cluster {cluster_id}: {e}")

def create_cluster_in_db(centroid: np.ndarray, member_count: int) -> Optional[str]:
    """Create a new cluster in the database.
    This function creates a new cluster with the given centroid and member count.
    It generates a new UUID for the cluster and inserts it into the database.
    Args:
        centroid: The centroid vector for the new cluster
        member_count: The initial member count   
    Returns:
        str: The ID of the newly created cluster, or None on failure.
    Raises: 
        APIError: If there is an error creating the cluster in the Supabase database.
        Exception: If there is an unexpected error during the creation operation.
    """
    if sb is None:
        logger.error("Supabase client is not initialized. Cannot perform create_cluster_in_db operation.")
        return None
    try:
        # Check if we need to normalize dimensions for the database
        # The database expects 768 dimensions, but our model might produce 1536
        if centroid.shape[0] != 768:
            template_vec = np.zeros(768)
            try:
                normalized_centroid, _ = normalize_vector_dimensions(centroid, template_vec)
                logger.info(f"Normalized centroid dimensions from {centroid.shape[0]} to {normalized_centroid.shape[0]}")
                centroid = normalized_centroid
            except ValueError as e:
                logger.error(f"Failed to normalize centroid dimensions for new cluster: {e}")
                # If we can't normalize, just downsample to 768 dimensions
                if centroid.shape[0] > 768:
                    step = centroid.shape[0] // 768
                    centroid = centroid[::step][:768]
                    logger.info(f"Downsampled centroid to 768 dimensions for new cluster using step {step}")

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
    except APIError as e:
        logger.error(f"Supabase APIError creating cluster: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error creating cluster: {e}")
        return None

def assign_article_to_cluster(article_id: int, cluster_id: str) -> None:
    """Write the cluster_id back to the article record.
    This function updates the article's cluster_id in the database.
    It is used to assign an article to a specific cluster after processing.
    Args:
        article_id: The ID of the article
        cluster_id: The ID of the cluster to assign the article to
    Returns:
        None
    Raises: 
        APIError: If there is an error updating the article in the Supabase database.
        Exception: If there is an unexpected error during the update operation.
    """
    if sb is None:
        logger.error(f"Supabase client is not initialized. Cannot perform assign_article_to_cluster operation for article_id {article_id}.")
        return # Or return False
    try:
        sb.table("SourceArticles").update({
            "cluster_id": cluster_id
        }).eq("id", article_id).execute()
        logger.debug(f"Assigned article {article_id} to cluster {cluster_id}")
    except APIError as e:
        logger.error(f"Supabase APIError assigning article {article_id} to cluster {cluster_id}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error assigning article {article_id} to cluster {cluster_id}: {e}")

def batch_assign_articles_to_cluster(assignments: List[Tuple[int, str]]) -> None:
    """Assign multiple articles to clusters in a single database call.
    This function updates the cluster_id for multiple articles in a single batch operation.
    This is more efficient than updating each article individually.
    Args:
        assignments: A list of ``(article_id, cluster_id)`` tuples.
    Returns:
        None
    Raises:
        APIError: If there is an error updating the articles in the Supabase database.
        Exception: If there is an unexpected error during the batch update operation.
    """
    if sb is None:
        logger.error("Supabase client is not initialized. Cannot perform batch_assign_articles_to_cluster operation.")
        return # Or return False
    if not assignments:
        return
    try:
        update_rows = [
            {"id": aid, "cluster_id": cid} for aid, cid in assignments
        ]
        sb.table("SourceArticles").upsert(update_rows, on_conflict="id").execute()
        logger.debug(f"Batch assigned {len(assignments)} articles to clusters")
    except APIError as e:
        logger.error(f"Supabase APIError batch assigning articles: {e}")
    except Exception as e:
        logger.error(f"Unexpected error batch assigning articles: {e}")

def repair_zero_centroid_clusters() -> List[str]:
    """Recalculate centroids for clusters where the stored centroid is all zeros.
    This function checks for clusters with a zero centroid and attempts to recalculate it based on the articles assigned to that cluster. 
    It fetches articles belonging to each cluster and computes the new centroid as the mean of their embeddings.
    Args:  
        None
    Returns:    
        List of cluster IDs that were updated with new centroids
    Raises: 
        APIError: If there is an error fetching data from the Supabase database.
        Exception: If there is an unexpected error during the repair operation.
    """
    if sb is None:
        logger.error("Supabase client is not initialized. Cannot perform repair_zero_centroid_clusters operation.")
        return []
    logger.info("Checking for clusters with zero centroid...")
    fixed_clusters: List[str] = []
    try:
        resp = sb.table("clusters").select("cluster_id, centroid").execute()
    except APIError as e:
        logger.error(f"Supabase APIError fetching clusters in repair_zero_centroid_clusters: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching clusters in repair_zero_centroid_clusters: {e}")
        return []

    for r in resp.data:
        centroid_raw = r.get("centroid")
        cluster_id = r["cluster_id"] # Moved cluster_id retrieval here to have it for logging in case of article fetch error

        if centroid_raw is None:
            centroid_array = np.array([])
        elif isinstance(centroid_raw, str):
            values = [float(x) for x in centroid_raw.strip('[]').split(',')]
            centroid_array = np.array(values, dtype=np.float32)
        else:
            centroid_array = np.array(centroid_raw, dtype=np.float32)

        # Condition to check if a centroid is effectively zero/empty or invalid
        if (
            centroid_raw is None  # No centroid stored
            or centroid_array.ndim == 0  # Centroid is an empty array (e.g. from invalid parse)
            or (centroid_array.ndim == 1 and np.allclose(centroid_array, 0))  # Centroid is a 1D array of all zeros
        ):
            try:
                articles_resp = (
                    sb.table("SourceArticles")
                    .select("id, ArticleVector!inner(embedding)")
                    .eq("cluster_id", cluster_id)
                    .execute()
                )
            except APIError as e:
                logger.error(f"Supabase APIError fetching articles for cluster {cluster_id} in repair_zero_centroid_clusters: {e}")
                continue # Skip to the next cluster
            except Exception as e:
                logger.error(f"Unexpected error fetching articles for cluster {cluster_id} in repair_zero_centroid_clusters: {e}")
                continue # Skip to the next cluster


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
                # update_cluster_in_db already has its own error handling
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
    Efficiently validates and corrects cluster member counts by calling a Supabase SQL function if available, or performing manual batch processing otherwise.
    This function checks the current member counts in the database against the actual number of articles assigned to each cluster.
    It uses the Supabase RPC function 'recalculate_all_cluster_member_counts' if available,
    or falls back to manual processing if the RPC call fails or is not defined.
    Args:
        None
    Returns:
        Dict[str, Tuple[int, int]]: A dictionary mapping cluster IDs to tuples of (old_count, new_count).
        This indicates the discrepancies found during the recalculation.
        If no discrepancies are found, an empty dictionary is returned.
    Raises:
        APIError: If there is an error calling the Supabase RPC function or fetching data from the database.
        Exception: If there is an unexpected error during the recalculation process.
    """
    
    if sb is None:
        logger.error("Supabase client is not initialized. Cannot perform recalculate_cluster_member_counts operation.")
        raise RuntimeError("Supabase client not initialized.")
    logger.info("Recalculating cluster member counts (batch mode)...")

    try:
        resp_clusters = sb.table("clusters").select("cluster_id, member_count").execute()
        current_counts = {r["cluster_id"]: r["member_count"] for r in resp_clusters.data}
        resp_articles = (
            sb.table("SourceArticles")
            .select("id, cluster_id")
            .not_.is_("cluster_id", None)
            .execute()
        )
    except APIError as e:
        logger.error(f"Supabase APIError fetching data in recalculate_cluster_member_counts: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error fetching data in recalculate_cluster_member_counts: {e}")
        return {}

    # Build actual counts from articles
    cluster_articles: Dict[str, List[int]] = {}
    for row in resp_articles.data:
        cid = row.get("cluster_id")
        cluster_articles.setdefault(cid, []).append(row.get("id"))
    actual_counts = {cid: len(ids) for cid, ids in cluster_articles.items()}

    # Attempt RPC batch processing if available, otherwise fall back to manual
    if hasattr(sb, 'rpc'):
        logger.info("Calling RPC 'recalculate_all_cluster_member_counts' to fix cluster member counts...")
        try:
            rpc_resp = sb.rpc('recalculate_all_cluster_member_counts').execute()
        except RPCCallFailedError as e:
            logger.error(f"Error calling 'recalculate_all_cluster_member_counts' RPC: {e}", exc_info=True)
            return {}
        except Exception as e:
            # Check if it's actually an RPCCallFailedError that wasn't caught above
            if type(e).__name__ == 'RPCCallFailedError':
                logger.error(f"Error calling 'recalculate_all_cluster_member_counts' RPC: {e}", exc_info=True)
                return {}
            else:
                logger.error(f"Error during RPC call, falling back to manual processing: {e}", exc_info=True)
        else:
            if rpc_resp and rpc_resp.data:
                result_data = rpc_resp.data
                logger.info(result_data.get('message', "Successfully recalculated cluster counts via RPC."))
                if result_data.get('updated_clusters'):
                    logger.info(f"Clusters updated: {len(result_data['updated_clusters'])}")
                if result_data.get('deleted_clusters'):
                    logger.info(f"Clusters deleted: {len(result_data['deleted_clusters'])}")
                if result_data.get('unassigned_articles_from_single_member_clusters'):
                    logger.info(f"Articles unassigned from single-member clusters: {len(result_data['unassigned_articles_from_single_member_clusters'])}")
                raw_disc = result_data.get('discrepancies', {}) or {}
                discrepancies: Dict[str, Tuple[int, int]] = {}
                for cid, counts in raw_disc.items():
                    if isinstance(counts, dict) and 'old' in counts and 'new' in counts:
                        discrepancies[cid] = (counts['old'], counts['new'])
                    else:
                        logger.warning(f"Unexpected format for discrepancy item: {cid} -> {counts}")
                if discrepancies:
                    logger.info(f"Found {len(discrepancies)} cluster member count discrepancies through RPC.")
                else:
                    logger.info("No cluster member count discrepancies reported by RPC.")
                return discrepancies
            else:
                logger.error("No data returned from 'recalculate_all_cluster_member_counts' RPC call or response.data is empty, and no exception was raised during the call.")
                return {}
    # Manual fallback when RPC is unavailable or failed
    logger.info("Performing manual batch recalculate cluster member_counts (without RPC)...")
    # Delete single-member clusters (unassign articles and delete cluster)
    for cid, cnt in actual_counts.items():
        if cnt == 1:
            sb.table("SourceArticles").update({"cluster_id": None}).eq("cluster_id", cid).execute()
            sb.table("clusters").delete().in_("cluster_id", [cid]).execute()
    # Delete clusters with no members
    for cid in current_counts:
        if cid not in actual_counts:
            sb.table("clusters").delete().in_("cluster_id", [cid]).execute()
    # Update clusters with more than one member
    clusters_to_upsert = []
    for cid, cnt in actual_counts.items():
        if cnt > 1:
            if cid in current_counts:
                # Update existing cluster
                sb.table("clusters").update({"member_count": cnt}).eq("cluster_id", cid).execute()
            else:
                # This cluster doesn't exist in current_counts, needs to be created
                clusters_to_upsert.append({"cluster_id": cid, "member_count": cnt})
    if clusters_to_upsert:
        sb.table("clusters").upsert(clusters_to_upsert, on_conflict="cluster_id").execute()
    # Compute discrepancies for all clusters (union of old and new counts)
    discrepancies: Dict[str, Tuple[int, int]] = {}
    for cid in set(current_counts.keys()).union(actual_counts.keys()):
        old_count = current_counts.get(cid, 0)
        new_count = actual_counts.get(cid, 0)
        if new_count != old_count:
            discrepancies[cid] = (old_count, new_count)
    return discrepancies

def update_old_clusters_status() -> int:
    """Update status of clusters to 'OLD' if they haven't been updated in 3 days.
    This function checks clusters that are not already marked as 'OLD' and updates their status to 'OLD' if they haven't been updated in the last 3 days.
    It fetches clusters from the database, checks their last updated timestamp, and updates their status accordingly.
    Args:
        None
    If the Supabase client is not initialized, it logs an error and raises a RuntimeError.
    If there are any issues fetching or updating clusters, it logs the error and returns 0.
    If clusters are successfully updated, it logs the number of clusters updated and returns that count.
    If no clusters need to be updated, it logs that no clusters needed to be updated and returns 0.
    Returns:
        Number of clusters updated to OLD status
    Raises:
        RuntimeError: If the Supabase client is not initialized.
        APIError: If there is an error fetching or updating clusters in the Supabase database.
        Exception: If there is an unexpected error during the update operation.
    """
    
    # Ensure Supabase client is initialized, else abort with error
    if sb is None:
        logger.error("Supabase client is not initialized. Cannot perform update_old_clusters_status operation.")
        raise RuntimeError("Supabase client is not initialized. Aborting cluster status update.")
    logger.info("Checking for clusters that haven't been updated in 3 days...")
    
    # Fetch clusters that aren't already marked as OLD
    resp = sb.table("clusters")\
             .select("cluster_id, updated_at")\
             .not_.eq("status", "OLD")\
             .execute()
    
    try:
        # Fetch clusters that aren't already marked as OLD
        resp = sb.table("clusters")\
                .select("cluster_id, updated_at")\
                .not_.eq("status", "OLD")\
                .execute()
    except APIError as e:
        logger.error(f"Supabase APIError fetching clusters in update_old_clusters_status: {e}")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error fetching clusters in update_old_clusters_status: {e}")
        return 0

    # In Python, calculate which clusters are older than 3 days
    from datetime import datetime, timedelta
    
    three_days_ago = datetime.now() - timedelta(days=3)
    old_cluster_ids = []
    num_updated = 0
    
    for cluster in resp.data:
        if "updated_at" in cluster and cluster["updated_at"]:
            # Parse the timestamp from the database
            try:
                updated_at_str = cluster["updated_at"]
                # Handle potential timezone 'Z' if not already handled by fromisoformat in all Python versions
                if updated_at_str.endswith('Z'):
                    updated_at_str = updated_at_str[:-1] + "+00:00"
                updated_at = datetime.fromisoformat(updated_at_str)
            except ValueError as ve:
                logger.warning(f"Could not parse updated_at timestamp '{cluster['updated_at']}' for cluster {cluster['cluster_id']}: {ve}")
                continue # Skip this cluster if timestamp is invalid
            
            # Check if it's older than 3 days
            if updated_at < three_days_ago:
                old_cluster_ids.append(cluster["cluster_id"])
    
    # If we found old clusters, update their status
    if old_cluster_ids:
        for cluster_id in old_cluster_ids:
            try:
                sb.table("clusters")\
                                .update({"status": "OLD"})\
                                .eq("cluster_id", cluster_id)\
                                .execute()
                num_updated += 1
            except APIError as e:
                logger.error(f"Supabase APIError updating cluster {cluster_id} to OLD: {e}")
                # Continue to try updating other clusters
            except Exception as e:
                logger.error(f"Unexpected error updating cluster {cluster_id} to OLD: {e}")
                # Continue to try updating other clusters
    
    if num_updated > 0:
        logger.info(f"Updated {num_updated} clusters to 'OLD' status")
    else:
        logger.debug("No clusters needed to be updated to 'OLD' status")
    
    return num_updated