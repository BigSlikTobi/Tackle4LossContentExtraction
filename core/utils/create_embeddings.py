from openai import OpenAI, APIError, APITimeoutError, RateLimitError, APIConnectionError, APIStatusError
import os
import sys
from dotenv import load_dotenv
from typing import List, Optional
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

def create_embedding(text: str, article_id: Optional[int] = None) -> Optional[List[float]]:
    """
    Create an embedding for the given text using OpenAI's API.
    Uses text-embedding-3-small which produces 1536D vectors.
    Returns None if an API error occurs.
    """
    try:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
            encoding_format="float"
        )
        return response.data[0].embedding
    except APITimeoutError as e:
        error_message = f"OpenAI APITimeoutError: {e}"
        if article_id:
            error_message += f" for article_id: {article_id}"
        print(error_message, file=sys.stderr)
        return None
    except RateLimitError as e:
        error_message = f"OpenAI RateLimitError: {e}"
        if article_id:
            error_message += f" for article_id: {article_id}"
        print(error_message, file=sys.stderr)
        return None
    except APIConnectionError as e:
        error_message = f"OpenAI APIConnectionError: {e}"
        if article_id:
            error_message += f" for article_id: {article_id}"
        print(error_message, file=sys.stderr)
        return None
    except APIStatusError as e:
        error_message = f"OpenAI APIStatusError: {e}"
        if article_id:
            error_message += f" for article_id: {article_id}"
        print(error_message, file=sys.stderr)
        return None
    except APIError as e:  # Catch-all for other OpenAI API errors
        error_message = f"OpenAI APIError: {e}"
        if article_id:
            error_message += f" for article_id: {article_id}"
        print(error_message, file=sys.stderr)
        return None
    except Exception as e: # General catch-all for other unexpected errors during embedding creation
        error_message = f"Unexpected error: {e}"
        if article_id:
            error_message += f" for article_id: {article_id}"
        print(error_message, file=sys.stderr)
        return None

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
        # response = supabase_client.table("ArticleVector").insert(data).execute() # Original
        supabase_client.table("ArticleVector").insert(data).execute() # Changed to not assign response as it's not used
        print(f"Successfully stored embedding for article {article_id}")
    except Exception as e:
        print(f"Error storing embedding for article_id {article_id}: {e}", file=sys.stderr)

def create_and_store_embedding(article_id: int, content: str) -> None:
    """
    Create and store an embedding for an article
    """
    try:
        embedding = create_embedding(content, article_id=article_id)
        if embedding is None:
            # Error already logged by create_embedding
            print(f"Embedding creation failed for article {article_id}, skipping storage.", file=sys.stderr)
            return

        normalized_embedding = normalize_embedding(embedding)
        store_embedding(article_id, normalized_embedding)
    except Exception as e:
        print(f"Error in create_and_store_embedding for article {article_id}: {e}", file=sys.stderr)