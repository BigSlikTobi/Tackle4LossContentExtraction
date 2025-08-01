"""
Extract content from unprocessed articles using a web crawler and LLM extraction strategy.
This module fetches unprocessed articles from the database, extracts their main content using a web crawler,
and saves the extracted content to a JSON file.
It uses the AsyncWebCrawler from the crawl4ai library and LLMExtractionStrategy for content extraction.
The extracted content is saved in a structured format for further processing or analysis.

Process:
1. Fetch unprocessed articles from the database.
2. For each article, extract the main content using the web crawler.
3. Save the extracted content to a JSON file.
"""

import os
import sys
import json
import asyncio
import time
import random
from urllib.parse import unquote
from crawl4ai import AsyncWebCrawler, CacheMode
from crawl4ai.extraction_strategy import LLMExtractionStrategy

from src.core.db.fetch_unprocessed_articles import get_unprocessed_articles
from src.core.utils.LLM_init import initialize_llm_client, ModelType

# Initialize the LLM client with configurable model type
MODEL_TYPE: ModelType = os.getenv("LLM_MODEL_TYPE", "gpt-4.1-nano-2025-04-14")
client, model_name = initialize_llm_client(model_type=MODEL_TYPE)
api_token = os.environ.get("OPENAI_API_KEY")  # Get API key from environment

async def extract_main_content(full_url: str) -> str:
    """
    Extract the main content from a web page using a web crawler and LLM extraction strategy.
    This function uses the AsyncWebCrawler to fetch the page and the LLMExtractionStrategy to extract the content.
    Args:
        full_url (str): The full URL of the article to extract content from.
    Returns:
        str: The extracted content as a string, or an error message if extraction fails.
    Raises:
        Exception: If there is an error during the extraction process.
    """
    try:
        async with AsyncWebCrawler(verbose=False) as crawler:
            # Create LLM strategy with text output instead of JSON
            max_tokens = int(os.getenv("EXTRACTION_MAX_TOKENS", "16000"))
            llm_strategy = LLMExtractionStrategy(
                llm_config={
                    "provider": f"openai/{model_name}",
                    "api_token": api_token,
                },
                verbose=True,
                max_tokens=max_tokens,
                temperature=1.0,
                word_count_threshold=50,
                exclude_tags=["footer", "header", "nav", "aside", "script", "style","img"],
                exclude_external_links=True,
                timeout=40,
                instructions="""
                    You are a content extractor. Extract the relevant text blocks
                    and return them in JSON format as a list of objects,
                    each with "tags" and "content".
                    Only include the core article content.
                """,
                output_format="text",
                max_retries=3  # This is likely a parameter for LLMExtractionStrategy's own retry for arun, not LLM timeout
            )
            # Add retry logic for API reliability
            max_attempts = 4  # Increased max attempts
            for attempt in range(max_attempts):
                try:
                    # Add jitter to avoid simultaneous requests
                    if attempt > 0:
                        jitter = random.uniform(0.5, 2.0)
                        wait_time = (2 ** attempt) + jitter  # Exponential backoff with jitter
                        print(f"API attempt {attempt+1}/{max_attempts}, waiting {wait_time:.1f} seconds...")
                        await asyncio.sleep(wait_time)
                    print(f"Attempting extraction (try {attempt+1}/{max_attempts})...")
                    result = await crawler.arun(
                        url=full_url,
                        extraction_strategy=llm_strategy,
                        max_pages=1,
                        cache_mode=CacheMode.WRITE_ONLY,
                    )
                    content = result.extracted_content
                    if content and len(content) > 50:  # Ensure meaningful content was returned
                        return content
                    else:
                        print(f"LLM returned insufficient content on attempt {attempt+1}")
                        # If this is the last attempt, return whatever we got
                        if attempt == max_attempts - 1:
                            print(f"Using best available content after all attempts")
                            return content if content else "No content could be extracted"
                except Exception as e:
                    error_str = str(e)
                    print(f"API error on attempt {attempt+1}: {error_str}")
                    # If this is the last attempt, return error info
                    if attempt == max_attempts - 1:
                        return f"Failed to extract content after {max_attempts} attempts. Last error: {error_str}"
                    # If it's a litellm error, let's try with different parameters
                    if "litellm.APIError" in error_str:
                        # Adjust strategy for next attempt to work around API limitations
                        # Assuming llm_strategy.instructions and llm_strategy.timeout are still valid attributes to set
                        llm_strategy.instructions = f"""
                            Attempt {attempt+2}: Extract text content from the web page.
                            Keep it simple and return plain text only.
                        """
                        # Cannot dynamically adjust timeout on the strategy object for this version.
                        # llm_strategy.timeout += 10 # This caused AttributeError
                        # If llm_config could be modified and strategy re-read it, that would be one way,
                        # but LLMConfig also doesn't take timeout.
                        # For now, removing dynamic timeout adjustment.

                        # If llm_config needs to be updated for retries (e.g. for temperature/max_tokens)
                        # new_config = llm_strategy.llm_config.copy() # If LLMConfig has a copy method
                        # new_config.temperature = max(0, new_config.temperature - 0.1) # Example
                        # llm_strategy.llm_config = new_config
                        # This part is speculative, current code only changes instructions and timeout.

            # If we reach here, all attempts failed
            return "Content extraction failed after multiple attempts"
    except Exception as e: # This will now catch errors from AsyncWebCrawler() or its __aenter__
        error_type = type(e).__name__
        error_message = str(e)
        log_message = f"[ERROR] Outer exception during extraction for {full_url}. Type: {error_type}, Message: {error_message}"
        print(log_message, file=sys.stderr) # Log to stderr for errors
        return f"Extraction failed for {full_url}. Type: {error_type}, Error: {error_message}"

async def main():
    """
    Main function to extract content from all unprocessed articles and save results to a JSON file.
    """
    # Load unprocessed articles
    unprocessed_articles = get_unprocessed_articles()
    extracted_contents = {}
    for article in unprocessed_articles:
        article_id = article["id"]
        # Normalize URL: use article["url"] if it starts with http; otherwise, prepend "https://www."
        url = article["url"]
        # URL decode the URL in case it's been URL-encoded
        url = unquote(url)
        article_url = url if url.startswith("http") else "https://www." + url
        print(f"Extracting content from {article_url}")
        try:
            extracted_content = await extract_main_content(article_url)
            if not extracted_content or extracted_content.startswith("Failed to extract"):
                print(f"Warning: Extraction issue for {article_url}")
            else:
                print(f"Successfully extracted {len(extracted_content)} characters from {article_url}")
        except Exception as e:
            print(f"[ERROR] Failed to extract content from {article_url}: {e}")
            extracted_content = f"Extraction error: {str(e)}"  # Store error message instead of empty string
        extracted_contents[article_id] = extracted_content
    # Store extracted contents
    with open("extracted_contents.json", "w") as f:
        json.dump(extracted_contents, f, indent=2)
    print("Content extraction complete.")

if __name__ == "__main__":
    asyncio.run(main())
