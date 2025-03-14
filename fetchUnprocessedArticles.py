import json
from typing import Dict, List
import supabase
from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file
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

if __name__ == "__main__":
    unprocessed_articles = get_unprocessed_articles()
    print(f"Found {len(unprocessed_articles)} unprocessed articles.")
