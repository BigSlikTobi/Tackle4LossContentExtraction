#!/usr/bin/env python3
"""
This script reads the extracted content from JSON and uses multiple LLM models to
extract and structure the content into a clean format.
"""
# TODO: Add -4o-mini for extraction tasks
# TODO: enable retry (3 times) for empty content extraction

import json
import os
import sys
import re
import datetime
from dateutil import parser
import logging
from typing import Dict, List, Any, Tuple, Optional
import tiktoken
from core.utils.LLM_init import initialize_llm_client, ModelType
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
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
    # In CI with what appears to be real credentials
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


# Initialize both LLM clients
deepseek_client, deepseek_model = initialize_llm_client(model_type="deepseek")
gpt4_client, gpt4_model = initialize_llm_client(model_type="gpt-4.1-nano-2025-04-14")

def load_extracted_content(file_path: str) -> Dict[str, Any]:
    """
    Load the extracted content from a JSON file.

    Args:
        file_path (str): Path to the JSON file containing extracted content.

    Returns:
        Dict[str, Any]: Dictionary containing the extracted content.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        print(f"Error loading extracted content: {e}")
        return {}

def clean_text(text: str) -> str:
    """
    Basic cleaning of text before sending to LLM.

    Args:
        text (str): The text to clean.

    Returns:
        str: Cleaned text.
    """
    # Remove image descriptions
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', text)
    # Remove extra backslashes
    text = text.replace('\\\\', '\\').replace('\\"', '"')
    # Remove links but keep text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def clean_publication_date(date_string: str) -> Optional[str]:
    """
    Convert publication date to PostgreSQL timestamptz format.

    Args:
        date_string (str): The original publication date string.

    Returns:
        Optional[str]: Formatted date string in timestamptz format or None if parsing fails.
    """
    if not date_string:
        return None
    try:
        # Try to parse the date string using dateutil parser
        parsed_date = parser.parse(date_string, fuzzy=True)
        # Format date as ISO 8601 format which is compatible with PostgreSQL timestamptz
        formatted_date = parsed_date.isoformat()
        return formatted_date
    except Exception as e:
        logging.error(f"Error parsing date '{date_string}': {e}")
        return None

def num_tokens(text: str, model: str) -> int:
    """Return the number of tokens in ``text`` for ``model``."""
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))

def chunk_text(text: str, max_tokens: int, model: str) -> List[str]:
    """Split ``text`` into chunks each with at most ``max_tokens`` tokens."""
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)
    chunks = [enc.decode(tokens[i:i + max_tokens]) for i in range(0, len(tokens), max_tokens)]
    return chunks

def extract_content_with_llm(content: str) -> Dict[str, str]:
    """Extract article content using the configured LLM.

    This function dynamically chunks content that exceeds the model token limit
    and merges the results so longer articles can be processed without
    truncation.
    """
    cleaned_content = clean_text(content)

    max_tokens = int(os.getenv("LLM_MAX_TOKENS", "16000"))
    chunk_size = max_tokens - 1000  # keep some headroom for the response
    chunks = chunk_text(cleaned_content, chunk_size, gpt4_model)

    results: List[Dict[str, str]] = []
    try:
        for idx, chunk in enumerate(chunks):
            if idx == 0:
                prompt = f"""You are a content extraction assistant. Given the article content below, extract the following fields and format them as a valid JSON object:

RULES:
- Return ONLY a valid JSON object with no additional text
- If a field is not found, use an empty string
- Remove any navigation elements, advertisements, or other non-article content
- Keep the original publication date format if found
- For authors, include their name/handle exactly as written

Example output format:
{{
    "title": "Example Article Title",
    "publication_date": "Mar 14, 2025",
    "author": "John Doe",
    "main_content": "The main article text..."
}}

Article content to process:
{chunk}"""
            else:
                prompt = f"""Continue extracting the main article content from the text below. Return ONLY a JSON object with a 'main_content' field.

Text:
{chunk}"""

            response = gpt4_client.chat.completions.create(
                model=gpt4_model,
                messages=[
                    {"role": "system", "content": "You are a content extraction assistant that outputs only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=1.0,
                max_tokens=max_tokens
            )
            response_text = response.choices[0].message.content.strip()
            if not response_text.startswith('{'):
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    response_text = response_text[json_start:json_end]
                else:
                    raise ValueError("No JSON object found in response")
            results.append(json.loads(response_text))
    except Exception as e:
        print(f"Error processing with LLM: {e}")
        print(f"Response text: {response_text if 'response_text' in locals() else 'No response'}")
        return {
            "title": "",
            "publication_date": "",
            "author": "",
            "main_content": cleaned_content,
        }

    title = results[0].get("title", "") if results else ""
    publication_date = results[0].get("publication_date", "") if results else ""
    author = results[0].get("author", "") if results else ""
    main_content = " ".join(r.get("main_content", "") for r in results)

    return {
        "title": title,
        "publication_date": publication_date,
        "author": author,
        "main_content": main_content,
    }

def analyze_content_type(content: Dict[str, str]) -> Dict[str, Any]:
    """
    Analyze the content and determine its category using Deepseek LLM.

    Uses Deepseek for its strong analytical capabilities.

    Args:
        content (Dict[str, str]): Dictionary containing the article content with title, main_content, and url.

    Returns:
        Dict[str, Any]: Dictionary with content type and confidence score.
    """
    # Check for news-round-up based on URL
    url = content.get("url", "")
    if "nfl-news-roundup" in url:
        return {
            "content_type": "news-round-up",
            "confidence": 1.0,
            "reasoning": "URL contains 'nfl-news-roundup' pattern"
        }
    # Prepare the content for analysis
    title = content.get("title", "")
    main_content = content.get("main_content", "")
    # Create a summary of the content for analysis
    content_summary = f"Title: {title}\n\nContent excerpt: {main_content[:1000]}..."
    prompt = f"""Analyze the following content and determine its category. Return a JSON object with the following fields:
    - content_type: One of ["news_article", "topic_collection", "news_collection", "empty_content", "news-round-up"]
    - confidence: A number between 0 and 1
    - reasoning: A brief explanation of why this category was chosen

Rules for categorization:
- news_article: A single coherent news article with a clear topic and narrative about one specific news or information
- topic_collection: A collection of related news snippets that all cover different stories about the same topic
- news_collection: A general collection of unrelated news items covering multiple topics
- news-round-up: A collection of NFL news updates typically found in roundup articles
- empty_content: Content that is too short, contains no meaningful information, or is clearly not a news article
- wrong_content: Content that is not covering the topic NFL American Football and is teherefore not relevant

Content to analyze:
{content_summary}"""
    try:
        # Using Deepseek for content analysis
        response = deepseek_client.chat.completions.create(
            model=deepseek_model,
            messages=[
                {"role": "system", "content": "You are a content analysis assistant that outputs only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Lower temperature for more consistent categorization
            max_tokens=1000
        )
        response_text = response.choices[0].message.content.strip()
        # Extract JSON from response
        if not response_text.startswith('{'):
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                response_text = response_text[json_start:json_end]
            else:
                raise ValueError("No JSON object found in response")
        result = json.loads(response_text)
        # Validate the content type
        valid_types = ["news_article", "topic_collection", "news_collection", "empty_content", "news-round-up"]
        if result.get("content_type") not in valid_types:
            raise ValueError(f"Invalid content type. Must be one of {valid_types}")
        return {
            "content_type": result.get("content_type"),
            "confidence": float(result.get("confidence", 0)),
            "reasoning": result.get("reasoning", "")
        }
    except Exception as e:
        print(f"Error analyzing content type: {e}")
        return {
            "content_type": "empty_content",
            "confidence": 1.0,
            "reasoning": f"Error during analysis: {str(e)}"
        }

def process_all_articles(extracted_data: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """
    Process all articles in the extracted data using LLM.

    Args:
        extracted_data (Dict[str, Any]): Dictionary of all extracted content.

    Returns:
        Dict[str, Dict[str, str]]: Dictionary of processed articles with article ID as key.
    """
    processed_articles = {}
    for article_id, content_data in extracted_data.items():
        try:
            # Combine all content sections into one string
            if isinstance(content_data, str):
                content = content_data
            else:
                # If it's a list of sections, join their content
                content = "\n\n".join(
                    "\n".join(section.get("content", []))
                    for section in content_data
                )
            # Process with LLM
            processed_article = extract_content_with_llm(content)
            # Clean date to timestamptz format if it's not empty
            if processed_article.get("publication_date"):
                processed_article["cleaned_date_timestamptz"] = clean_publication_date(processed_article["publication_date"])
            else:
                processed_article["cleaned_date_timestamptz"] = None
            # Analyze content type
            content_analysis = analyze_content_type(processed_article)
            processed_article["content_type"] = content_analysis["content_type"]
            processed_article["type_confidence"] = content_analysis["confidence"]
            processed_article["type_reasoning"] = content_analysis["reasoning"]
            processed_articles[article_id] = processed_article
            # Print summary of what was extracted for debugging
            print(f"Processed article {article_id}:")
            print(f"  Title: {processed_article['title'][:70]}..." if len(processed_article['title']) > 70 else f"  Title: {processed_article['title']}")
            print(f"  Date: {processed_article['publication_date']}")
            if processed_article["cleaned_date_timestamptz"]:
                print(f"  Cleaned Date: {processed_article['cleaned_date_timestamptz']}")
            print(f"  Author: {processed_article['author']}")
            print(f"  Content length: {len(processed_article['main_content'])} chars")
            print(f"  Content type: {processed_article['content_type']} (confidence: {processed_article['type_confidence']:.2f})")
            print()
        except Exception as e:
            print(f"Error processing article {article_id}: {e}")
    return processed_articles

def save_cleaned_content(cleaned_data: Dict[str, Dict[str, str]], output_file: str) -> None:
    """
    Save the cleaned content to a JSON file.

    Args:
        cleaned_data (Dict[str, Dict[str, str]]): Dictionary of cleaned articles.
        output_file (str): Path to the output file.
    """
    try:
        with open(output_file, 'w', encoding='utf-8') as file:
            json.dump(cleaned_data, file, indent=2)
        print(f"Cleaned content saved to {output_file}")
    except Exception as e:
        print(f"Error saving cleaned content: {e}")

def update_article_in_db(article_id: int, update_data: Dict[str, Any]) -> None:
    """
    Update an article's data in the Supabase database.

    Args:
        article_id (int): The ID of the article to update.
        update_data (Dict[str, Any]): The data to update.
    """
    if not supabase_client:
        logging.warning(f"Supabase client not initialized. Skipping update for article {article_id}.")
        return
    try:
        response = supabase_client.table("SourceArticles").update(update_data).eq("id", article_id).execute()
        if response.data:
            logging.info(f"Article {article_id} updated successfully.")
        else:
            logging.warning(f"No article found with id {article_id}. Update skipped.")
    except Exception as e:
        logging.error(f"Error updating article {article_id} in database: {e}")

def update_existing_articles_content_type() -> None:
    """
    Check and update content types for all existing articles in the database.

    Particularly useful for applying new content type rules to existing articles.
    """
    try:
        # Fetch all processed articles from the database
        response = supabase_client.table("SourceArticles").select("*").eq("isProcessed", True).execute()
        articles = response.data
        if not articles:
            print("No processed articles found in the database.")
            return
        print(f"Found {len(articles)} processed articles to check.")
        updated_count = 0
        for article in articles:
            try:
                # Create content dictionary for analyze_content_type
                content_data = {
                    "title": article.get("title", ""),
                    "main_content": article.get("Content", ""),
                    "url": article.get("url", "")
                }
                # Analyze content type
                content_analysis = analyze_content_type(content_data)
                # Only update if the content type would change
                if content_analysis["content_type"] != article.get("contentType"):
                    update_data = {
                        "contentType": content_analysis["content_type"]
                    }
                    # Update the article in the database
                    supabase_client.table("SourceArticles").update(update_data).eq("id", article["id"]).execute()
                    updated_count += 1
                    print(f"Updated article {article['id']}:")
                    print(f"  Old content type: {article.get('contentType')}")
                    print(f"  New content type: {content_analysis['content_type']}")
                    print(f"  Confidence: {content_analysis['confidence']:.2f}")
                    print(f"  Reasoning: {content_analysis['reasoning']}")
                    print()
            except Exception as e:
                print(f"Error processing article {article.get('id')}: {e}")
                continue
        print(f"\nUpdate complete. Modified {updated_count} out of {len(articles)} articles.")
    except Exception as e:
        print(f"Error fetching articles from database: {e}")

def main():
    """
    Main function to load, process, and save cleaned article content.
    """
    # File paths
    input_file = os.path.join(os.path.dirname(__file__), 'extracted_contents.json')
    output_file = os.path.join(os.path.dirname(__file__), 'cleaned_contents.json')
    # Load extracted content
    extracted_data = load_extracted_content(input_file)
    if not extracted_data:
        print("No data found in the extracted content file.")
        return
    # Process articles
    cleaned_articles = process_all_articles(extracted_data)
    # Save cleaned content
    save_cleaned_content(cleaned_articles, output_file)
    # Summary
    print(f"Processed {len(cleaned_articles)} articles.")
    # Count articles with empty fields
    empty_titles = sum(1 for article in cleaned_articles.values() if not article["title"])
    empty_dates = sum(1 for article in cleaned_articles.values() if not article["publication_date"])
    empty_content = sum(1 for article in cleaned_articles.values() if not article["main_content"])
    print(f"Articles with empty titles: {empty_titles}")
    print(f"Articles with empty dates: {empty_dates}")
    print(f"Articles with empty content: {empty_content}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--update-content-types":
        update_existing_articles_content_type()
    else:
        main()