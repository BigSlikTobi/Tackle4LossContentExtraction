# core/db/fetch_unprocessed_articles.py
"""
Database logic for fetching unprocessed SourceArticles.
This module connects to a Supabase database to retrieve articles that have not been processed yet.
It handles the connection setup, error handling, and data retrieval.
"""
from supabase import create_client, Client
import os
import sys
from dotenv import load_dotenv
from typing import Dict, List, Optional

# Try to load from .env file, but GitHub Actions will use environment variables directly
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase_client: Optional[Client] = None
IS_CI = os.getenv("CI") == 'true' or os.getenv("GITHUB_ACTIONS") == 'true'

# Initialize Supabase client only if credentials are available and valid
if SUPABASE_URL and SUPABASE_KEY and not IS_CI:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"WARNING: Failed to initialize Supabase client: {e}")
        supabase_client = None
elif IS_CI and SUPABASE_URL and SUPABASE_KEY and not SUPABASE_KEY.startswith('test-'):
    # In CI with real credentials
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"WARNING: Failed to initialize Supabase client in CI: {e}")
        supabase_client = None
elif not IS_CI and (not SUPABASE_URL or not SUPABASE_KEY):
    # Exit only if not in a CI environment and missing credentials
    print("ERROR: SUPABASE_URL and/or SUPABASE_KEY environment variables are not set.")
    sys.exit(1)
else:
    # In CI with test credentials or other cases - just log and continue
    print("WARNING: Supabase credentials not available or in CI mode. Running without database access.")


def get_unprocessed_articles() -> List[Dict]:
    """
    Fetches SourceArticles records where isProcessed = false.
    This function retrieves articles that have not been processed yet.
    Args:
        None
    Returns:
        List[Dict]: A list of dictionaries representing unprocessed articles.
    Raises:
        Exception: If there is an error fetching data from Supabase.
    """
    if not supabase_client:
        print("Supabase client not initialized. Returning empty list for unprocessed articles.")
        return []
    try:
        response = supabase_client.table("SourceArticles").select("*").eq("isProcessed", False).execute()
        return response.data or []
    except Exception as e:
        print(f"Error fetching unprocessed items from Supabase: {e}")
        return []
