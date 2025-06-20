# core/db/update_article.py
"""
Database update logic for SourceArticles table.
"""
# Import supabase_client from the new location
from Tackle4LossContentExtraction.core.db.fetch_unprocessed_articles import supabase_client
from typing import Dict, Any

def update_article_in_db(article_id: int, update_data: Dict[str, Any]) -> bool:
    """
    Update the SourceArticles table for a given article ID.

    Args:
        article_id: The ID of the article to update.
        update_data: Dictionary of columns and values to update.

    Returns:
        True if update was successful, False otherwise.
    """
    try:
        response = supabase_client.table("SourceArticles").update(update_data).eq("id", article_id).execute()
        if response.data:
            return True
        else:
            return False
    except Exception as e:
        print(f"[ERROR] Failed to update database for article {article_id}: {e}")
        return False
