from openai import OpenAI, APIError, APITimeoutError, RateLimitError, APIConnectionError, APIStatusError
import os
import sys # Keep sys for sys.stderr for now, though logger is preferred
from dotenv import load_dotenv
from typing import List, Optional
from supabase import create_client, Client
import numpy as np  # Add numpy for vector normalization
import logging

logger = logging.getLogger(__name__)
# Basic configuration for the logger if no other logging is set up in the project
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', stream=sys.stderr)


load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client
openai_client_instance: Optional[OpenAI] = None
if OPENAI_API_KEY:
    openai_client_instance = OpenAI(api_key=OPENAI_API_KEY)
else:
    logger.warning("OPENAI_API_KEY not found in environment. OpenAI client-dependent functions will not be functional.")

# Initialize Supabase client
supabase_client: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        # supabase_client remains None
else:
    logger.warning("SUPABASE_URL or SUPABASE_KEY not found in environment. Supabase client-dependent functions will not be functional.")


def create_embedding(text: str, article_id: Optional[int] = None) -> Optional[List[float]]:
    """
    Create an embedding for the given text using OpenAI's API.
    Uses text-embedding-3-small which produces 1536D vectors.
    Returns None if an API error occurs or if the client is not initialized.
    """
    if openai_client_instance is None:
        logger.error("OpenAI client is not initialized (likely missing API key). Cannot create embedding for article_id: %s.", article_id)
        return None
    # Check for api_key attribute specifically, though client being None should cover it.
    if not getattr(openai_client_instance, 'api_key', None):
         logger.error("OpenAI client is not configured with an API key. Cannot create embedding for article_id: %s.", article_id)
         return None

    try:
        response = openai_client_instance.embeddings.create(
            model="text-embedding-3-small",
            input=text,
            encoding_format="float"
        )
        return response.data[0].embedding
    except APITimeoutError as e:
        logger.error("OpenAI APITimeoutError for article_id %s: %s", article_id, e)
        return None
    except RateLimitError as e:
        logger.error("OpenAI RateLimitError for article_id %s: %s", article_id, e)
        return None
    except APIConnectionError as e:
        logger.error("OpenAI APIConnectionError for article_id %s: %s", article_id, e)
        return None
    except APIStatusError as e: # Handles 4xx status codes from OpenAI
        logger.error("OpenAI APIStatusError (e.g. 4xx) for article_id %s: %s", article_id, e)
        return None
    except APIError as e:  # Catch-all for other OpenAI API errors (e.g. 5xx)
        logger.error("OpenAI APIError (e.g. 5xx) for article_id %s: %s", article_id, e)
        return None
    except Exception as e: # General catch-all for other unexpected errors
        logger.error("Unexpected error during embedding creation for article_id %s: %s", article_id, e, exc_info=True)
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
    if supabase_client is None:
        logger.error("Supabase client not initialized. Cannot store embedding for article_id %s.", article_id)
        return

    try:
        data = {
            "embedding": embedding, # Type: List[float]
            "SourceArticle": article_id # Type: int
        }
        # The 'embedding' column in Supabase should be of type vector(1536) or similar
        supabase_client.table("ArticleVector").insert(data).execute()
        logger.info("Successfully stored embedding for article %s", article_id)
    except Exception as e: # Catching generic Exception, consider more specific ones if known (e.g. PostgrestAPIError)
        logger.error("Error storing embedding for article_id %s: %s", article_id, e, exc_info=True)

def create_and_store_embedding(article_id: int, content: str) -> None:
    """
    Create and store an embedding for an article
    """
    # No try-except needed here anymore if sub-functions handle their errors and log them.
    # This function becomes an orchestrator.
    embedding = create_embedding(content, article_id=article_id)

    if embedding is None:
        # Error should have been logged by create_embedding
        # We could add an info log here if needed, e.g.,
        # logger.info("Embedding creation failed for article %s, skipping storage.", article_id)
        # The problem description asks for create_and_store_embedding to log if create_embedding returns None.
        # create_embedding now logs its own errors, so this might be redundant or just an info.
        # The previous print to stderr is now covered by create_embedding's logger.error.
        # Let's add an info log here for clarity of workflow stoppage.
        logger.info("Embedding creation failed for article %s (see previous errors), skipping storage.", article_id)
        return

    try:
        normalized_embedding = normalize_embedding(embedding)
        store_embedding(article_id, normalized_embedding)
    except Exception as e:
        # This catch block is for unexpected errors in normalize_embedding or during the call to store_embedding,
        # though store_embedding now also has its own internal error handling.
        logger.error("Error during embedding normalization or dispatching to storage for article %s: %s", article_id, e, exc_info=True)