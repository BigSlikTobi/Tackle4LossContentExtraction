#!/usr/bin/env python3
"""
This script reads the extracted content from JSON and uses multiple LLM models to
extract and structure the content into a clean format.
"""
# TODO: Add -4o-mini for extraction tasks
# TODO: enable retry (3 times) for empty content extraction

import json
import os
import re
import datetime
from dateutil import parser
import logging
from typing import Dict, List, Any, Tuple, Optional
from core.utils.LLM_init import initialize_llm_client, ModelType
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize both LLM clients
deepseek_client, deepseek_model = initialize_llm_client(model_type="deepseek")
gpt4_client, gpt4_model = initialize_llm_client(model_type="gpt-4.1-nano-2025-04-14")

def load_extracted_content(file_path: str) -> Dict[str, Any]:
    """
    Load the extracted content from a JSON file.
    
    Args:
        file_path: Path to the JSON file containing extracted content
        
    Returns:
        Dictionary containing the extracted content
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
        text: The text to clean
        
    Returns:
        Cleaned text
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
        date_string: The original publication date string
        
    Returns:
        Formatted date string in timestamptz format or None if parsing fails
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

def extract_content_with_llm(content: str) -> Dict[str, str]:
    """
    Extract article content using gpt-4.1-nano-2025-04-14 for better extraction capabilities.
    
    Args:
        content: The raw content to process
        
    Returns:
        Dictionary with title, date, author, and content
    """
    # Clean the content first
    cleaned_content = clean_text(content)
    
    # Construct the prompt for the LLM
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
{cleaned_content}"""

    try:
        # Using gpt-4.1-nano-2025-04-14 for content extraction
        response = gpt4_client.chat.completions.create(
            model=gpt4_model,
            messages=[
                {"role": "system", "content": "You are a content extraction assistant that outputs only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=1.0,  
            max_tokens=16000  
        )
        
        # Get the response text
        response_text = response.choices[0].message.content.strip()
        
        # Ensure we're only trying to parse the JSON part
        if not response_text.startswith('{'):
            # Try to find JSON object in the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                response_text = response_text[json_start:json_end]
            else:
                raise ValueError("No JSON object found in response")
        
        # Parse the JSON response
        result = json.loads(response_text)
        
        # Ensure all required fields are present
        return {
            "title": result.get("title", ""),
            "publication_date": result.get("publication_date", ""),
            "author": result.get("author", ""),
            "main_content": result.get("main_content", "")
        }
        
    except Exception as e:
        print(f"Error processing with LLM: {e}")
        print(f"Response text: {response.choices[0].message.content if 'response' in locals() else 'No response'}")
        # Fallback to returning cleaned content
        return {
            "title": "",
            "publication_date": "",
            "author": "",
            "main_content": cleaned_content
        }

def analyze_content_type(content: Dict[str, str]) -> Dict[str, Any]:
    """
    Analyze the content and determine its category using Deepseek LLM.
    Uses Deepseek for its strong analytical capabilities.
    
    Args:
        content: Dictionary containing the article content with title, main_content, and url
        
    Returns:
        Dictionary with content type and confidence score
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
        extracted_data: Dictionary of all extracted content
        
    Returns:
        Dictionary of processed articles with article ID as key
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
        cleaned_data: Dictionary of cleaned articles
        output_file: Path to the output file
    """
    try:
        with open(output_file, 'w', encoding='utf-8') as file:
            json.dump(cleaned_data, file, indent=2)
        print(f"Cleaned content saved to {output_file}")
    except Exception as e:
        print(f"Error saving cleaned content: {e}")

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