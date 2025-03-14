from openai import OpenAI
import os
from dotenv import load_dotenv
from typing import List
from supabase import create_client, Client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

client = OpenAI()

def create_embedding(text: str) -> List[float]:
    """
    Create an embedding for the given text using OpenAI's API.
    Uses text-embedding-3-small which produces 1536D vectors.
    """
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
        encoding_format="float"
    )
    return response.data[0].embedding

def store_embedding(article_id: int, embedding: List[float]) -> None:
    """
    Store the embedding in the ArticleVector table
    """
    try:
        data = {
            "embedding": embedding,
            "SourceArticle": article_id
        }
        response = supabase_client.table("ArticleVector").insert(data).execute()
        print(f"Successfully stored embedding for article {article_id}")
    except Exception as e:
        print(f"Error storing embedding: {e}")

def create_and_store_embedding(article_id: int, content: str) -> None:
    """
    Create and store an embedding for an article
    """
    try:
        embedding = create_embedding(content)
        store_embedding(article_id, embedding)
    except Exception as e:
        print(f"Error creating/storing embedding for article {article_id}: {e}")