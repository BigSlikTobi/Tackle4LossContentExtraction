#!/usr/bin/env python3
"""
Debug script to understand why the integration test is failing.
"""
import uuid
import sys
import os

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath('.'))

from core.clustering.db_access import recalculate_cluster_member_counts, init_supabase_client
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Supabase client
sb = init_supabase_client()
if sb is None:
    print("Failed to initialize Supabase client. Make sure .env is configured.")
    sys.exit(1)

def setup_test_data():
    """Set up test data similar to the failing test."""
    # Create unique cluster IDs
    c1_id = str(uuid.uuid4())
    print(f"Creating test cluster: {c1_id}")
    
    # Create cluster with member_count = 5
    cluster_data = {
        "cluster_id": c1_id,
        "member_count": 5,
        "centroid": [0.1] * 768,
        "status": "UPDATED"
    }
    
    try:
        cluster_insert_res = sb.table("clusters").insert(cluster_data).execute()
        print(f"Cluster insert response: {cluster_insert_res}")
    except Exception as e:
        print(f"Error inserting cluster: {e}")
        return None, []
    
    # Create 2 articles associated with this cluster
    article_ids = [2000, 2001]  # Use high IDs to avoid conflicts
    articles_data = []
    for aid in article_ids:
        articles_data.append({
            "id": aid,
            "cluster_id": c1_id,
            "url": f"http://test{aid}.com",
            "isProcessed": True
        })
    
    try:
        for article_data in articles_data:
            article_insert_res = sb.table("SourceArticles").insert(article_data).execute()
            print(f"Article {article_data['id']} insert response: {article_insert_res}")
    except Exception as e:
        print(f"Error inserting articles: {e}")
        # Continue with test even if article insertion fails
    
    return c1_id, article_ids

def check_data_before(c1_id):
    """Check the data before calling recalculate function."""
    print("\n=== BEFORE RECALCULATION ===")
    
    # Check cluster
    cluster_res = sb.table("clusters").select("*").eq("cluster_id", c1_id).execute()
    print(f"Cluster data: {cluster_res.data}")
    
    # Check articles
    articles_res = sb.table("SourceArticles").select("id, cluster_id").eq("cluster_id", c1_id).execute()
    print(f"Articles data: {articles_res.data}")
    print(f"Number of articles: {len(articles_res.data)}")

def check_data_after(c1_id):
    """Check the data after calling recalculate function."""
    print("\n=== AFTER RECALCULATION ===")
    
    # Check cluster
    cluster_res = sb.table("clusters").select("*").eq("cluster_id", c1_id).execute()
    print(f"Cluster data: {cluster_res.data}")
    
    # Check articles
    articles_res = sb.table("SourceArticles").select("id, cluster_id").eq("cluster_id", c1_id).execute()
    print(f"Articles data: {articles_res.data}")
    print(f"Number of articles: {len(articles_res.data)}")

def cleanup_test_data(c1_id, article_ids):
    """Clean up test data."""
    print(f"\n=== CLEANUP ===")
    try:
        if article_ids:
            sb.table("SourceArticles").delete().in_("id", article_ids).execute()
            print(f"Deleted articles: {article_ids}")
        
        if c1_id:
            sb.table("clusters").delete().eq("cluster_id", c1_id).execute()
            print(f"Deleted cluster: {c1_id}")
    except Exception as e:
        print(f"Error during cleanup: {e}")

def main():
    """Main debug function."""
    print("=== DEBUG TEST FOR RECALCULATE CLUSTER MEMBER COUNTS ===")
    
    # Setup test data
    c1_id, article_ids = setup_test_data()
    if c1_id is None:
        print("Failed to set up test data. Exiting.")
        return
    
    try:
        # Check data before
        check_data_before(c1_id)
        
        # Call the function
        print("\n=== CALLING RECALCULATE FUNCTION ===")
        discrepancies = recalculate_cluster_member_counts()
        print(f"Discrepancies returned: {discrepancies}")
        
        # Check data after
        check_data_after(c1_id)
        
    finally:
        # Cleanup
        cleanup_test_data(c1_id, article_ids)

if __name__ == "__main__":
    main()
