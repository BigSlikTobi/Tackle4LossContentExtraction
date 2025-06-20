from openai import OpenAI
import os
import sys
from dotenv import load_dotenv
from typing import List
from supabase import create_client, Client
import numpy as np  # Add numpy for vector normalization

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

def normalize_embedding(embedding: List[float]) -> List[float]:
    """
    Normalize an embedding vector to have unit length (L2 norm)
    """
    embedding_array = np.array(embedding)
    norm = np.linalg.norm(embedding_array)
    if norm > 0:
        normalized = embedding_array / norm
    else:
        normalized = embedding_array
    return normalized.tolist()

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
        normalized_embedding = normalize_embedding(embedding)
        store_embedding(article_id, normalized_embedding)
    except Exception as e:
        print(f"Error creating/storing embedding for article {article_id}: {e}")