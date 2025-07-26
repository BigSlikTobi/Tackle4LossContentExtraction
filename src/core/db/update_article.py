# core/db/update_article.py
"""
Database update logic for SourceArticles table.
This module provides functionality to update articles in the SourceArticles table.
It connects to a Supabase database and handles the update operations.
"""
import logging # Import logging module

# Import the Supabase client from the fetch_unprocessed_articles module
from src.core.db.fetch_unprocessed_articles import supabase_client
from typing import Dict, Any

logger = logging.getLogger(__name__) # Get logger instance

def update_article_in_db(article_id: int, update_data: Dict[str, Any]) -> bool:
    """
    Update the SourceArticles table for a given article ID.
    This function updates the specified columns of an article in the database.
    Args:
        article_id: The ID of the article to update.
        update_data: Dictionary of columns and values to update.
    Returns:
        True if update was successful, False otherwise.
    Raises:
        Exception: If there is an error updating the article in the database.
    """
    try:
        response = supabase_client.table("SourceArticles").update(update_data).eq("id", article_id).execute()
        # Check if response.error exists (using get to avoid AttributeError if error is not present)
        error = getattr(response, 'error', None)
        if error:
            logger.error(f"Failed to update database for article {article_id}: {error}")
            return False
        else:
            # Assuming no error means success. The problem description implies this,
            # but in a real scenario, we might want to check response.data as well,
            # depending on Supabase client behavior.
            return True
    except Exception as e:
        logger.error(f"Failed to update database for article {article_id}: {e}")
        return False
