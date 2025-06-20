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
from postgrest.exceptions import APIError # Import Postgrest APIError

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
    # sys.exit(1) # Avoid sys.exit during testing; sb will be None and tests should mock it.

def fetch_unclustered_articles() -> List[Tuple[int, np.ndarray]]:
    """Fetch articles without a cluster_id from the database.
    
    Returns:
        List of tuples with article ID and embedding vector
    """
    if sb is None:
        logger.error("Supabase client is not initialized. Cannot perform fetch_unclustered_articles operation.")
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
    
    Returns:
        List of tuples with cluster ID, centroid vector, and member count
    """
    if sb is None:
        logger.error("Supabase client is not initialized. Cannot perform fetch_existing_clusters operation.")
        return []
    logger.info("Fetching existing clusters...")
    clusters = []
    try:
        resp = sb.table("clusters")\
                .select("cluster_id, centroid, member_count")\
                .execute()

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
    except APIError as e:
        logger.error(f"Supabase APIError in fetch_existing_clusters: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in fetch_existing_clusters: {e}")
        return []
    return clusters

def update_cluster_in_db(cluster_id: str, new_centroid: np.ndarray, new_count: int, isContent: bool = False) -> None:
    """Update an existing cluster in the database.
    
    Args:
        cluster_id: The ID of the cluster to update
        new_centroid: The updated centroid vector
        new_count: The updated member count
        isContent: Whether the cluster has content associated with it
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
    
    Args:
        centroid: The centroid vector for the new cluster
        member_count: The initial member count
        
    Returns:
        str: The ID of the newly created cluster, or None on failure.
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
    
    Args:
        article_id: The ID of the article
        cluster_id: The ID of the cluster to assign the article to
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

    Args:
        assignments: A list of ``(article_id, cluster_id)`` tuples.
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

    Returns a list of cluster IDs that were updated.
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
    """Efficiently validate and correct cluster member counts.

    The previous implementation queried each cluster individually which was
    extremely chatty with the database. This version fetches all article
    assignments in a single request and then performs batched updates and
    deletions.  It returns a dictionary mapping the cluster ID to a tuple of
    ``(old_count, new_count)`` for every cluster whose count changed.
    """
    if sb is None:
        logger.error("Supabase client is not initialized. Cannot perform recalculate_cluster_member_counts operation.")
        return {}
    logger.info("Recalculating cluster member counts (batch mode)...")
    discrepancies: Dict[str, Tuple[int, int]] = {}

    try:
        # Fetch current cluster counts
        clusters_resp = sb.table("clusters").select("cluster_id, member_count").execute()
        current_counts = {r["cluster_id"]: r["member_count"] for r in clusters_resp.data}

        # Fetch all article assignments in one request
        articles_resp = (
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


    cluster_articles: Dict[str, List[int]] = {}
    for row in articles_resp.data:
        cid = row["cluster_id"]
        cluster_articles.setdefault(cid, []).append(row["id"])

    actual_counts = {cid: len(ids) for cid, ids in cluster_articles.items()}

    updates: List[Dict[str, object]] = []
    empty_clusters: List[str] = []
    single_member_clusters: Dict[str, int] = {}

    all_cluster_ids = set(current_counts.keys()) | set(actual_counts.keys())

    for cid in all_cluster_ids:
        actual = actual_counts.get(cid, 0)
        old = current_counts.get(cid, 0)

        if old != actual:
            discrepancies[cid] = (old, actual)

        if actual >= 2:
            if actual != old:
                updates.append({
                    "cluster_id": cid,
                    "member_count": actual,
                    "updated_at": "now()",
                })
        elif actual == 1:
            single_member_clusters[cid] = cluster_articles[cid][0]
        else:
            empty_clusters.append(cid)

    try:
        if updates:
            sb.table("clusters").upsert(updates, on_conflict="cluster_id").execute()
            logger.info(f"Updated member counts for {len(updates)} clusters")
    except APIError as e:
        logger.error(f"Supabase APIError updating cluster counts in recalculate_cluster_member_counts: {e}")
    except Exception as e:
        logger.error(f"Unexpected error updating cluster counts in recalculate_cluster_member_counts: {e}")

    try:
        if empty_clusters:
            sb.table("clusters").delete().in_("cluster_id", empty_clusters).execute()
            logger.info(f"Deleted {len(empty_clusters)} empty clusters")
    except APIError as e:
        logger.error(f"Supabase APIError deleting empty clusters in recalculate_cluster_member_counts: {e}")
    except Exception as e:
        logger.error(f"Unexpected error deleting empty clusters in recalculate_cluster_member_counts: {e}")

    if single_member_clusters:
        article_ids_to_unassign = list(single_member_clusters.values())
        cluster_ids_to_delete = list(single_member_clusters.keys())
        try:
            sb.table("SourceArticles").update({"cluster_id": None}).in_("id", article_ids_to_unassign).execute()
            logger.info(f"Unassigned {len(article_ids_to_unassign)} articles from single-member clusters.")
        except APIError as e:
            logger.error(f"Supabase APIError unassigning articles from single-member clusters: {e}")
        except Exception as e:
            logger.error(f"Unexpected error unassigning articles from single-member clusters: {e}")

        try:
            sb.table("clusters").delete().in_("cluster_id", cluster_ids_to_delete).execute()
            logger.info(f"Deleted {len(cluster_ids_to_delete)} single-member clusters")
        except APIError as e:
            logger.error(f"Supabase APIError deleting single-member clusters: {e}")
        except Exception as e:
            logger.error(f"Unexpected error deleting single-member clusters: {e}")


    if discrepancies:
        logger.info(f"Fixed {len(discrepancies)} cluster member count discrepancies")
    else:
        logger.info("All cluster member counts are accurate")

    return discrepancies

def update_old_clusters_status() -> int:
    """Update status of clusters to 'OLD' if they haven't been updated in 3 days.
    
    Returns:
        Number of clusters updated to OLD status
    """
    if sb is None:
        logger.error("Supabase client is not initialized. Cannot perform update_old_clusters_status operation.")
        return 0
    logger.info("Checking for clusters that haven't been updated in 3 days...")
    num_updated = 0
    
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