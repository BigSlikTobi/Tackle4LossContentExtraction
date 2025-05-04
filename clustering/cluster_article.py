""" 
This function fetches unclustered articles and existing clusters from the database.
It first tries to match unclustered articles to existing clusters based on cosine similarity.
If no match is found, it pairs up remaining unclustered articles to form new clusters.
Finally, it updates the database with the new cluster assignments.
"""

import uuid
import numpy as np
from supabase import create_client
from dotenv import load_dotenv
import os
import logging
from typing import Dict, List, Tuple

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# In-memory cache for singleton articles pending a match
pending: Dict[int, np.ndarray] = {}


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors of possibly different dimensions.
    If dimensions don't match, the longer vector is downsampled to match the shorter one.
    """
    # Handle dimension mismatch
    if a.shape[0] != b.shape[0]:
        # If a is twice as long as b, downsample a
        if a.shape[0] == b.shape[0] * 2:
            a = a[::2]
        # If b is twice as long as a, downsample b
        elif b.shape[0] == a.shape[0] * 2:
            b = b[::2]
        else:
            raise ValueError(f"Incompatible dimensions: {a.shape[0]} and {b.shape[0]}")
            
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def fetch_unclustered() -> List[Tuple[int, np.ndarray]]:
    """Fetch articles without a cluster_id from the database."""
    logger.info("Fetching unclustered articles...")
    resp = (
        sb.table("SourceArticles")
          .select("id, ArticleVector!inner(embedding)")
          .is_("cluster_id", None)
          .eq("contentType", "news_article")
          .order("created_at", desc=True)  # Sort by created_at in descending order to get newest articles first
          .limit(1000)  # Explicitly set limit to 1000 (Supabase's maximum)
          .execute()
    )
    articles = []
    for r in resp.data:
        article_id = r["id"]
        emb_str = r["ArticleVector"][0]["embedding"]
        values = [float(x) for x in emb_str.strip('[]').split(',')]
        articles.append((article_id, np.array(values, dtype=np.float32)))
    logger.info(f"Found {len(articles)} unclustered articles")
    return articles


def fetch_clusters() -> List[Tuple[str, np.ndarray, int]]:
    """Fetch existing clusters with their centroids and counts."""
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


def update_cluster(cluster_id: str, old_cent: np.ndarray, old_count: int, new_vec: np.ndarray) -> Tuple[np.ndarray, int]:
    """Incrementally update a cluster's centroid and count."""
    logger.debug(f"Updating cluster {cluster_id} (members {old_count} -> {old_count+1})")
    
    # Handle dimension mismatch
    if old_cent.shape[0] != new_vec.shape[0]:
        # If new_vec is twice as long as old_cent, downsample new_vec
        if new_vec.shape[0] == old_cent.shape[0] * 2:
            new_vec = new_vec[::2]
        # If old_cent is twice as long as new_vec, downsample old_cent (unlikely)
        elif old_cent.shape[0] == new_vec.shape[0] * 2:
            old_cent = old_cent[::2]
        else:
            raise ValueError(f"Incompatible dimensions: {old_cent.shape[0]} and {new_vec.shape[0]}")
    
    centroid = (old_cent * old_count + new_vec) / (old_count + 1)
    sb.table("clusters").update({
        "centroid": centroid.tolist(),
        "member_count": old_count + 1,
        "updated_at": "now()"
    }).eq("cluster_id", cluster_id).execute()
    return centroid, old_count + 1


def create_cluster(vectors: List[np.ndarray]) -> Tuple[str, np.ndarray, int]:
    """Create a new cluster from a list of vectors."""
    cid = str(uuid.uuid4())
    logger.info(f"Seeding new cluster {cid} with {len(vectors)} articles")
    centroid = np.mean(np.vstack(vectors), axis=0)
    # Downsample if 1536 -> 768 dims
    if centroid.shape[0] == 1536:
        centroid = centroid[::2]
    sb.table("clusters").insert({
        "cluster_id": cid,
        "centroid": centroid.tolist(),
        "member_count": len(vectors)
    }).execute()
    return cid, centroid, len(vectors)


def assign_article(article_id: int, cluster_id: str) -> None:
    """Write the cluster_id back to the article record."""
    sb.table("SourceArticles").update({"cluster_id": cluster_id}).eq("id", article_id).execute()


def process_new(threshold: float = 0.82) -> None:
    """Process each unclustered article with upsert-style clustering."""
    logger.info(f"Clustering run started (threshold={threshold})")
    to_cluster = fetch_unclustered()
    clusters = fetch_clusters()

    for article_id, vec in to_cluster:
        # 1) Try existing clusters
        best_score = threshold
        best = None
        for cid, cent, count in clusters:
            score = cosine_similarity(vec, cent)
            if score > best_score:
                best_score = score
                best = (cid, cent, count)

        if best:
            cid, cent, count = best
            new_cent, new_count = update_cluster(cid, cent, count, vec)
            # update in-memory cluster
            clusters = [
                (c, new_cent, new_count) if c == cid else (c, ce, ct)
                for c, ce, ct in clusters
            ]
            assign_article(article_id, cid)
            continue

        # 2) Try pending singletons
        pend_id, pend_cent = None, None
        for pid, pvec in pending.items():
            score = cosine_similarity(vec, pvec)
            if score > best_score:
                best_score = score
                pend_id, pend_cent = pid, pvec

        if pend_id:
            # Promote to new cluster
            cid, new_cent, new_count = create_cluster([pend_cent, vec])
            assign_article(pend_id, cid)
            assign_article(article_id, cid)
            # cleanup pending
            del pending[pend_id]
            # add to clusters
            clusters.append((cid, new_cent, new_count))
            continue

        # 3) No match: stash in pending
        pending[article_id] = vec

    logger.info("Clustering run complete")


if __name__ == "__main__":
    process_new()
