"""
This script fetches article embeddings from the database that were stored in the last 48 hours,
compares them to find similarities, and outputs pairs of similar articles to the terminal.
It also updates the duplication_of field in the SourceArticles table based on NewsSource hierarchy.
"""
import os
import json
import numpy as np
from typing import List, Dict, Tuple, Any
from datetime import datetime, timedelta, UTC
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables and set up Supabase client
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Similarity threshold - articles with cosine similarity above this value will be considered similar
SIMILARITY_THRESHOLD = 0.85

# Primary NewsSource IDs in order of precedence
PRIMARY_NEWS_SOURCE_ID = 1
SECONDARY_NEWS_SOURCE_ID = 2

def fetch_recent_embeddings() -> List[Dict[str, Any]]:
    """
    Fetch embeddings created in the last 48 hours from the ArticleVector table,
    using the created_at timestamp from the SourceArticles table.
    Only includes articles that aren't already marked as duplicates.
    
    Returns:
        List of dictionaries containing embedding data
    """
    # Calculate timestamp for 48 hours ago using timezone-aware datetime
    cutoff_time = (datetime.now(UTC) - timedelta(hours=48)).isoformat()
    
    try:
        # First get recent non-duplicate article IDs
        articles_response = supabase_client.table("SourceArticles") \
            .select("id") \
            .gte("created_at", cutoff_time) \
            .is_("duplication_of", "null") \
            .execute()
            
        if not articles_response.data:
            print("No non-duplicate articles found from the last 48 hours")
            return []
            
        recent_article_ids = [article["id"] for article in articles_response.data]
        
        # Then get embeddings for those articles
        embeddings_response = supabase_client.table("ArticleVector") \
            .select("id, embedding, SourceArticle") \
            .in_("SourceArticle", recent_article_ids) \
            .execute()
        
        if not embeddings_response.data:
            print("No embeddings found for non-duplicate articles created in the last 48 hours")
            return []
            
        print(f"Found {len(embeddings_response.data)} embeddings from non-duplicate articles created in the last 48 hours")
        return embeddings_response.data
    except Exception as e:
        print(f"Error fetching embeddings from database: {e}")
        return []

def parse_embedding(embedding_data: Any) -> List[float]:
    """
    Parse embedding data from the database into a list of floats.
    
    Args:
        embedding_data: Raw embedding data from the database
        
    Returns:
        List of floating point numbers representing the embedding
    """
    try:
        # If it's a string, try to parse it as JSON
        if isinstance(embedding_data, str):
            return json.loads(embedding_data)
        # If it's already a list, validate its contents are numeric
        elif isinstance(embedding_data, list):
            return [float(x) for x in embedding_data]
        else:
            raise ValueError(f"Unexpected embedding data type: {type(embedding_data)}")
    except Exception as e:
        raise ValueError(f"Failed to parse embedding data: {e}")

def calculate_cosine_similarity(embedding1: List[float], embedding2: List[float]) -> float:
    """
    Calculate cosine similarity between two embeddings.
    
    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector
        
    Returns:
        Cosine similarity score between 0 and 1
    """
    try:
        # Parse embeddings if needed
        vec1 = np.array(parse_embedding(embedding1))
        vec2 = np.array(parse_embedding(embedding2))
        
        # Calculate cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        # Handle zero vectors
        if norm1 == 0 or norm2 == 0:
            return 0
            
        return dot_product / (norm1 * norm2)
    except Exception as e:
        print(f"Error calculating similarity: {e}")
        return 0

def find_similar_articles(embeddings: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], Dict[str, Any], float]]:
    """
    Compare all embeddings with each other to find similar articles.
    
    Args:
        embeddings: List of embedding dictionaries
        
    Returns:
        List of tuples containing pairs of similar articles and their similarity score
    """
    similar_pairs = []
    total_comparisons = len(embeddings) * (len(embeddings) - 1) // 2
    comparison_count = 0
    
    print(f"Comparing {total_comparisons} embedding pairs...")
    
    for i in range(len(embeddings)):
        for j in range(i + 1, len(embeddings)):
            comparison_count += 1
            if comparison_count % 100 == 0:
                print(f"Progress: {comparison_count}/{total_comparisons} comparisons")
                
            # Skip if same source article
            if embeddings[i]["SourceArticle"] == embeddings[j]["SourceArticle"]:
                continue
                
            # Calculate similarity
            similarity = calculate_cosine_similarity(embeddings[i]["embedding"], embeddings[j]["embedding"])
            
            # If similarity is above threshold, add to similar pairs
            if similarity >= SIMILARITY_THRESHOLD:
                similar_pairs.append((embeddings[i], embeddings[j], similarity))
    
    return similar_pairs

def fetch_article_details(article_ids: List[int]) -> Dict[int, Dict[str, Any]]:
    """
    Fetch article details for a list of article IDs.
    
    Args:
        article_ids: List of article IDs
        
    Returns:
        Dictionary mapping article IDs to their details
    """
    if not article_ids:
        return {}
        
    try:
        # Fetch article details including source
        response = supabase_client.table("SourceArticles").select(
            "id, url, Content, Author, contentType, source, duplication_of"
        ).in_("id", article_ids).execute()
        
        # Map article IDs to details
        return {article["id"]: {
            "title": article["Content"][:100] + "..." if len(article["Content"]) > 100 else article["Content"],
            "url": article["url"],
            "contentType": article["contentType"],
            "Author": article.get("Author", "Unknown"),
            "NewsSource": article["source"],  # Still using NewsSource in our code but mapping from source column
            "duplication_of": article.get("duplication_of")
        } for article in response.data}
    except Exception as e:
        print(f"Error fetching article details: {e}")
        return {}

def determine_primary_article(article1: Dict[str, Any], article2: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Determine which article should be considered the primary source based on NewsSource hierarchy.
    
    Returns:
        Tuple of (primary_article, duplicate_article)
    """
    # If either article is from NewsSource 1, it's the primary
    if article1["NewsSource"] == PRIMARY_NEWS_SOURCE_ID:
        return article1, article2
    if article2["NewsSource"] == PRIMARY_NEWS_SOURCE_ID:
        return article2, article1
        
    # If either article is from NewsSource 2, it's the primary (unless the other was from NewsSource 1)
    if article1["NewsSource"] == SECONDARY_NEWS_SOURCE_ID:
        return article1, article2
    if article2["NewsSource"] == SECONDARY_NEWS_SOURCE_ID:
        return article2, article1
        
    # For other cases, use the article with the lower ID as primary
    if article1["id"] < article2["id"]:
        return article1, article2
    return article2, article1

def update_duplicate_articles(similar_pairs: List[Tuple[Dict[str, Any], Dict[str, Any], float]], article_details: Dict[int, Dict[str, Any]]) -> None:
    """
    Update the duplication_of field in the SourceArticles table for duplicate articles.
    
    Args:
        similar_pairs: List of tuples containing pairs of similar articles and their similarity score
        article_details: Dictionary mapping article IDs to their details
    """
    updates_made = 0
    
    for emb1, emb2, similarity in similar_pairs:
        article1_id = emb1["SourceArticle"]
        article2_id = emb2["SourceArticle"]
        
        article1 = article_details.get(article1_id)
        article2 = article_details.get(article2_id)
        
        if not article1 or not article2:
            continue
            
        # Skip if either article is already marked as a duplicate
        if article1.get("duplication_of") or article2.get("duplication_of"):
            continue
            
        # Determine primary article based on NewsSource hierarchy
        primary, duplicate = determine_primary_article(
            {"id": article1_id, "NewsSource": article1["NewsSource"]},
            {"id": article2_id, "NewsSource": article2["NewsSource"]}
        )
        
        try:
            # Update the duplicate article with reference to the primary
            update_data = {"duplication_of": primary["id"]}
            response = supabase_client.table("SourceArticles") \
                .update(update_data) \
                .eq("id", duplicate["id"]) \
                .execute()
                
            if response.data:
                updates_made += 1
                print(f"Updated article {duplicate['id']} as duplicate of {primary['id']}")
                print(f"  Similarity: {similarity:.4f}")
                print(f"  Primary from NewsSource: {primary['NewsSource']}")
                print(f"  Duplicate from NewsSource: {duplicate['NewsSource']}")
        except Exception as e:
            print(f"Error updating duplication status: {e}")
    
    print(f"\nDuplication updates complete. Updated {updates_made} articles.")

def print_similar_articles(similar_pairs: List[Tuple[Dict[str, Any], Dict[str, Any], float]]) -> None:
    """
    Print similar article pairs to the terminal and update duplication status.
    
    Args:
        similar_pairs: List of tuples containing pairs of similar articles and their similarity score
    """
    if not similar_pairs:
        print("\nNo similar articles found.")
        return
        
    # Get all article IDs from similar pairs
    article_ids = set()
    for emb1, emb2, _ in similar_pairs:
        article_ids.add(emb1["SourceArticle"])
        article_ids.add(emb2["SourceArticle"])
    
    # Fetch article details
    article_details = fetch_article_details(list(article_ids))
    
    # Update duplicate articles in the database
    update_duplicate_articles(similar_pairs, article_details)
    
    # Print similar pairs
    print(f"\nFound {len(similar_pairs)} similar article pairs:")
    print("-" * 80)
    
    for i, (emb1, emb2, similarity) in enumerate(similar_pairs, 1):
        article1_id = emb1["SourceArticle"]
        article2_id = emb2["SourceArticle"]
        
        article1 = article_details.get(article1_id, {"title": "Unknown", "url": "Unknown"})
        article2 = article_details.get(article2_id, {"title": "Unknown", "url": "Unknown"})
        
        print(f"Pair {i}:")
        print(f"  Similarity: {similarity:.4f}")
        print(f"  Article 1: [{article1_id}] {article1.get('title', 'Unknown')}")
        print(f"    URL: {article1.get('url', 'Unknown')}")
        print(f"    Type: {article1.get('contentType', 'Unknown')}")
        print(f"    NewsSource: {article1.get('NewsSource', 'Unknown')}")
        print(f"  Article 2: [{article2_id}] {article2.get('title', 'Unknown')}")
        print(f"    URL: {article2.get('url', 'Unknown')}")
        print(f"    Type: {article2.get('contentType', 'Unknown')}")
        print(f"    NewsSource: {article2.get('NewsSource', 'Unknown')}")
        print("-" * 80)

def main():
    """
    Main function to run the similarity comparison and update duplications.
    """
    print("Fetching recent embeddings...")
    embeddings = fetch_recent_embeddings()
    
    if not embeddings:
        return
        
    print("Finding similar articles...")
    similar_pairs = find_similar_articles(embeddings)
    
    print_similar_articles(similar_pairs)
    
    # Summary
    print(f"\nSummary:")
    print(f"  Embeddings analyzed: {len(embeddings)}")
    print(f"  Similar article pairs found: {len(similar_pairs)}")
    print(f"  Similarity threshold: {SIMILARITY_THRESHOLD}")

if __name__ == "__main__":
    main()