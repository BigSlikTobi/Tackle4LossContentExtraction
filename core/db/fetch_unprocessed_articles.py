# core/db/fetch_unprocessed_articles.py
"""
Database logic for fetching unprocessed SourceArticles.
"""
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from typing import Dict, List

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
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
