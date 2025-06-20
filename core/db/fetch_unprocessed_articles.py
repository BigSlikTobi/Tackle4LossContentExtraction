# core/db/fetch_unprocessed_articles.py
"""
Database logic for fetching unprocessed SourceArticles.
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

# Initialize Supabase client only if credentials are available
if SUPABASE_URL and SUPABASE_KEY:
    supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
elif not IS_CI:
    # Exit only if not in a CI environment
    print("ERROR: SUPABASE_URL and/or SUPABASE_KEY environment variables are not set.")
    sys.exit(1)
else:
    # In CI without credentials, so log a warning.
    print("WARNING: Supabase credentials not found. Running in CI mode without database access.")


def get_unprocessed_articles() -> List[Dict]:
    """
    Fetches SourceArticles records where isProcessed = false.
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
