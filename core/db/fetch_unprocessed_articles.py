# core/db/fetch_unprocessed_articles.py
"""
Database logic for fetching unprocessed SourceArticles.
"""
from supabase import create_client, Client
import os
import sys
from dotenv import load_dotenv
from typing import Dict, List

# Try to load from .env file, but GitHub Actions will use environment variables directly
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Check if the required environment variables are set
if not SUPABASE_URL:
    print("ERROR: SUPABASE_URL environment variable is not set")
    sys.exit(1)
if not SUPABASE_KEY:
    print("ERROR: SUPABASE_KEY environment variable is not set")
    sys.exit(1)

# Initialize Supabase client only after validating credentials exist
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_unprocessed_articles() -> List[Dict]:
    """
    Fetches SourceArticles records where isProcessed = false.
    """
    try:
        response = supabase_client.table("SourceArticles").select("*").eq("isProcessed", False).execute()
        return response.data or []
    except Exception as e:
        print(f"Error fetching unprocessed items from Supabase: {e}")
        return []
