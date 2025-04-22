#!/usr/bin/env python3
"""
This script fetches recent 'news_article' type articles,
clusters them based on embedding similarity using DBSCAN,
and updates their 'cluster_id' in the database.
"""

import os
import json
import uuid
import numpy as np
from typing import List, Dict, Tuple, Any, Optional
from datetime import datetime, timedelta, UTC
from dotenv import load_dotenv
from supabase import create_client, Client
from sklearn.cluster import DBSCAN

# Load environment variables and set up Supabase client
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase URL or Key not found in environment variables.")

supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Utility Function (from find_similar_articles.py) ---

def parse_embedding(embedding_data: Any) -> List[float]:
    """
    Parse embedding data from the database into a list of floats.

    Args:
        embedding_data: Raw embedding data from the database

    Returns:
        List of floating point numbers representing the embedding

    Raises:
        ValueError: If parsing fails or data type is unexpected.
    """
    try:
        # If it's a string, try to parse it as JSON
        if isinstance(embedding_data, str):
            # Handle potential variations in string format (e.g., direct list string)
            try:
                # Attempt direct JSON parsing first
                parsed = json.loads(embedding_data)
                if isinstance(parsed, list):
                    return [float(x) for x in parsed]
            except json.JSONDecodeError:
                # Fallback for simple string representation like '[1.0, 2.0]'
                if embedding_data.startswith('[') and embedding_data.endswith(']'):
                    cleaned_str = embedding_data.strip('[]')
                    if cleaned_str: # Ensure not empty after stripping
                       return [float(x.strip()) for x in cleaned_str.split(',')]
                    else:
                       return [] # Return empty list if string was just '[]'
                else:
                    raise ValueError("Embedding string is not valid JSON or list format")

        # If it's already a list, validate its contents are numeric
        elif isinstance(embedding_data, list):
            return [float(x) for x in embedding_data]
        else:
            raise ValueError(f"Unexpected embedding data type: {type(embedding_data)}")
    except Exception as e:
        # Add original data type to error for clarity
        raise ValueError(f"Failed to parse embedding data (type: {type(embedding_data)}): {e}")


# --- Clustering Core Functions ---

def fetch_embeddings_for_clustering(
    time_window_days: int = 10,
    content_type: str = 'news_article'
) -> List[Dict[str, Any]]:
    """
    Fetch embeddings for non-duplicate articles of a specific content type
    created within the specified time window.

    Args:
        time_window_days: How many days back to fetch articles from.
        content_type: The specific 'contentType' to filter articles by.

    Returns:
        List of dictionaries, each containing 'article_id' and 'embedding'.
        Returns an empty list if no suitable articles or embeddings are found.
    """
    print(f"Fetching articles from the last {time_window_days} days with contentType='{content_type}'...")
    # Calculate cutoff timestamp (timezone-aware)
    cutoff_time = (datetime.now(UTC) - timedelta(days=time_window_days)).isoformat()

    try:
        # 1. Get IDs of relevant articles
        articles_response = supabase_client.table("SourceArticles") \
            .select("id") \
            .gte("created_at", cutoff_time) \
            .eq("contentType", content_type) \
            .is_("duplication_of", "null") \
            .execute()

        if not articles_response.data:
            print("No non-duplicate articles found matching the criteria.")
            return []

        article_ids = [article["id"] for article in articles_response.data]
        print(f"Found {len(article_ids)} candidate articles.")

        # 2. Get embeddings for those articles
        print(f"Fetching embeddings for {len(article_ids)} articles...")
        embeddings_response = supabase_client.table("ArticleVector") \
            .select("SourceArticle, embedding") \
            .in_("SourceArticle", article_ids) \
            .execute()

        if not embeddings_response.data:
            print("No embeddings found for the selected articles.")
            return []

        print(f"Found {len(embeddings_response.data)} embeddings.")

        # 3. Prepare data structure and parse embeddings
        embeddings_data = []
        skipped_parsing = 0
        for row in embeddings_response.data:
            try:
                embedding = parse_embedding(row["embedding"])
                embeddings_data.append({
                    "article_id": row["SourceArticle"],
                    "embedding": embedding
                })
            except ValueError as e:
                skipped_parsing += 1
                print(f"Warning: Skipping embedding for article {row['SourceArticle']} due to parsing error: {e}")

        if skipped_parsing > 0:
            print(f"Skipped {skipped_parsing} embeddings due to parsing errors.")

        print(f"Successfully prepared {len(embeddings_data)} embeddings for clustering.")
        return embeddings_data

    except Exception as e:
        print(f"Error fetching data for clustering: {e}")
        return []


def perform_dbscan_clustering(
    embeddings_data: List[Dict[str, Any]],
    eps: float = 0.25, # Cosine distance threshold (1 - similarity)
    min_samples: int = 2
) -> Dict[int, int]:
    """
    Performs DBSCAN clustering on the provided embeddings.

    Args:
        embeddings_data: List of dicts {'article_id': id, 'embedding': [float_list]}.
        eps: The maximum distance (cosine distance) between two samples for
             one to be considered as in the neighborhood of the other.
        min_samples: The number of samples in a neighborhood for a point
                     to be considered as a core point.

    Returns:
        A dictionary mapping article_id to its cluster label (int).
        Label -1 indicates noise.
    """
    if not embeddings_data:
        print("No embeddings data provided for clustering.")
        return {}

    print(f"Performing DBSCAN clustering with eps={eps}, min_samples={min_samples}...")

    article_ids = [item["article_id"] for item in embeddings_data]
    # Ensure embeddings are numpy array of correct type
    try:
        X = np.array([item["embedding"] for item in embeddings_data], dtype=np.float32)
        if X.ndim != 2 or X.shape[1] == 0:
             raise ValueError(f"Embeddings array has unexpected shape: {X.shape}")
    except Exception as e:
        print(f"Error converting embeddings to NumPy array: {e}")
        # Optionally, identify which embedding caused the issue if possible
        for i, item in enumerate(embeddings_data):
            try:
                np.array(item["embedding"], dtype=np.float32)
            except Exception as inner_e:
                print(f" -> Problematic embedding at index {i} for article_id {item['article_id']}: {inner_e}")
        return {}


    # Check for empty embeddings array after potential errors
    if X.shape[0] == 0:
        print("Embeddings array is empty after processing. Cannot cluster.")
        return {}

    # Configure and run DBSCAN
    # Using 'cosine' metric means eps is cosine distance (1 - similarity)
    dbscan = DBSCAN(eps=eps, min_samples=min_samples, metric='cosine', n_jobs=-1)

    try:
        db = dbscan.fit(X)
    except Exception as e:
        print(f"Error during DBSCAN fitting: {e}")
        return {}

    labels = db.labels_ # Cluster labels for each point (-1 for noise)

    # Count clusters and noise
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = list(labels).count(-1)
    print(f'Estimated number of clusters: {n_clusters}')
    print(f'Estimated number of noise points: {n_noise}')

    # Map article IDs to cluster labels
    article_cluster_labels = {article_id: int(label) for article_id, label in zip(article_ids, labels)}

    return article_cluster_labels


def generate_cluster_uuids(article_cluster_labels: Dict[int, int]) -> Dict[int, str]:
    """
    Generates unique UUIDs for each cluster label found (excluding noise).

    Args:
        article_cluster_labels: Mapping from article_id to cluster label.

    Returns:
        A dictionary mapping cluster label (int >= 0) to a unique UUID string.
    """
    if not article_cluster_labels:
        return {}

    # Find unique cluster labels (excluding -1 for noise)
    unique_labels = set(label for label in article_cluster_labels.values() if label != -1)

    # Generate a UUID for each unique cluster label
    cluster_uuids = {label: str(uuid.uuid4()) for label in unique_labels}

    print(f"Generated {len(cluster_uuids)} unique UUIDs for clusters.")
    return cluster_uuids


def prepare_cluster_updates(
    article_cluster_labels: Dict[int, int],
    cluster_uuids: Dict[int, str]
) -> List[Dict[str, Any]]:
    """
    Prepares a list of dictionaries for updating the 'cluster_id' in the database.

    Args:
        article_cluster_labels: Mapping from article_id to cluster label.
        cluster_uuids: Mapping from cluster label (>=0) to UUID string.

    Returns:
        List of update dictionaries: [{'id': article_id, 'cluster_id': uuid_or_none}, ...]
    """
    updates = []
    for article_id, label in article_cluster_labels.items():
        cluster_update_value: Optional[str] = None
        if label != -1:
            # Assign the UUID corresponding to the cluster label
            cluster_update_value = cluster_uuids.get(label)
            if cluster_update_value is None:
                 print(f"Warning: No UUID found for cluster label {label} (article {article_id}). Setting cluster_id to NULL.")

        # Prepare the update dictionary for this article
        updates.append({'id': article_id, 'cluster_id': cluster_update_value})

    return updates


def update_article_clusters(updates: List[Dict[str, Any]]) -> int:
    """
    Updates the 'cluster_id' for articles in the SourceArticles table.

    Args:
        updates: List of update dictionaries from prepare_cluster_updates.

    Returns:
        The number of successfully updated articles.
    """
    if not updates:
        print("No cluster updates to perform.")
        return 0

    print(f"Attempting to update cluster IDs for {len(updates)} articles...")
    successful_updates = 0

    for update_data in updates:
        article_id = update_data['id']
        cluster_id = update_data['cluster_id'] # This can be UUID string or None

        try:
            # Use update() method
            response = supabase_client.table("SourceArticles") \
                .update({'cluster_id': cluster_id}) \
                .eq('id', article_id) \
                .execute()

            # Check if the update was successful (Supabase typically returns data on success)
            # Note: response structure might vary; adjust check if needed.
            # A check on len(response.data) might be suitable if it returns the updated row(s).
            # Or check for errors if the API throws them explicitly.
            # Assuming success if no exception is raised for simplicity here.
            # Add more robust checking based on actual Supabase client behavior if needed.
            successful_updates += 1

        except Exception as e:
            print(f"Error updating cluster for article {article_id}: {e}")
            # Decide if you want to stop or continue on error
            # continue

    print(f"Successfully updated cluster IDs for {successful_updates}/{len(updates)} articles.")
    return successful_updates


def run_clustering_pipeline(
    time_window_days: int = 10,
    eps: float = 0.25,
    min_samples: int = 2
) -> None:
    """
    Runs the full article clustering pipeline.

    Args:
        time_window_days: How many days back to fetch articles.
        eps: DBSCAN epsilon (cosine distance).
        min_samples: DBSCAN min_samples.
    """
    print("\n--- Starting Article Clustering Pipeline ---")
    start_time = datetime.now()

    # 1. Fetch Embeddings
    embeddings_data = fetch_embeddings_for_clustering(time_window_days=time_window_days)
    if not embeddings_data:
        print("Pipeline halted: No embeddings found to cluster.")
        return

    # 2. Perform Clustering
    article_cluster_labels = perform_dbscan_clustering(
        embeddings_data,
        eps=eps,
        min_samples=min_samples
    )
    if not article_cluster_labels:
        print("Pipeline halted: Clustering step failed.")
        return

    # 3. Generate Cluster UUIDs
    cluster_uuids = generate_cluster_uuids(article_cluster_labels)

    # 4. Prepare Updates
    updates_to_perform = prepare_cluster_updates(article_cluster_labels, cluster_uuids)

    # 5. Update Database
    update_count = update_article_clusters(updates_to_perform)

    end_time = datetime.now()
    print(f"--- Article Clustering Pipeline Finished ---")
    print(f"Total time: {end_time - start_time}")
    print(f"Articles processed: {len(article_cluster_labels)}")
    print(f"Database cluster_id fields updated: {update_count}")
    print(f"Parameters: time_window={time_window_days} days, eps={eps}, min_samples={min_samples}")


if __name__ == "__main__":
    # Example usage: Run the pipeline directly
    # You might want to adjust parameters based on experimentation
    run_clustering_pipeline(
        time_window_days=10,
        eps=0.25, # Cosine distance threshold (lower = higher similarity required)
                 # 0.25 corresponds to a cosine similarity of 0.75
        min_samples=2 # Minimum 2 articles needed to form a cluster
    )