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
    """Update a cluster's centroid and member count in the database.
    
    Args:
        cluster_id: The ID of the cluster to update
        new_centroid: The updated centroid vector
        new_count: The updated member count
        isContent: Whether the cluster has content associated with it
    """
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
        The ID of the newly created cluster
    """
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
    """Efficiently validate and correct cluster member counts.

    The previous implementation queried each cluster individually which was
    extremely chatty with the database. This version fetches all article
    assignments in a single request and then performs batched updates and
    deletions.  It returns a dictionary mapping the cluster ID to a tuple of
    ``(old_count, new_count)`` for every cluster whose count changed.
    """

    logger.info("Recalculating cluster member counts (batch mode)...")

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

    cluster_articles: Dict[str, List[int]] = {}
    for row in articles_resp.data:
        cid = row["cluster_id"]
        cluster_articles.setdefault(cid, []).append(row["id"])

    actual_counts = {cid: len(ids) for cid, ids in cluster_articles.items()}

    discrepancies: Dict[str, Tuple[int, int]] = {}
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

    if updates:
        sb.table("clusters").upsert(updates, on_conflict="cluster_id").execute()
        logger.info(f"Updated member counts for {len(updates)} clusters")

    if empty_clusters:
        sb.table("clusters").delete().in_("cluster_id", empty_clusters).execute()
        logger.info(f"Deleted {len(empty_clusters)} empty clusters")

    if single_member_clusters:
        article_ids = list(single_member_clusters.values())
        sb.table("SourceArticles").update({"cluster_id": None}).in_("id", article_ids).execute()
        sb.table("clusters").delete().in_("cluster_id", list(single_member_clusters.keys())).execute()
        logger.info(f"Removed {len(single_member_clusters)} single-member clusters")

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