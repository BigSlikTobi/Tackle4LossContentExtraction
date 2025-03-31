"""
This script is the main pipeline for processing unprocessed articles.
For each article:
1. Fetch unprocessed articles from the database
2. Extract the main content from each article
3. Clean and structure the content
4. Update the database with processed content (unless in debug mode)
"""
import asyncio
import sys
import os
import time
from typing import Dict, Any

# Add the parent directory to the Python path to allow for absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the necessary modules
from fetchUnprocessedArticles import get_unprocessed_team_articles, supabase_client
from extractContent import extract_main_content
from cleanContent import extract_content_with_llm, analyze_content_type
from LLM_init import initialize_llm_client

# Initialize the LLM client from the shared module
client = initialize_llm_client()

# Debug flag - set to True to skip database updates and print results instead
DEBUG = False

async def process_article(article: Dict[str, Any], debug: bool = DEBUG) -> Dict[str, Any]:
    """
    Process a single article through the entire pipeline:
    1. Extract content
    2. Clean and structure content
    3. Update the database (unless in debug mode)
    
    Args:
        article: Dictionary containing article information
        debug: If True, skips database updates and prints results instead
        
    Returns:
        Dictionary with processed article information
    """
    article_id = article["id"]
    # Normalize URL: use article["url"] if it starts with http; otherwise, prepend "https://www."
    url = article["url"]
    article_url = url if url.startswith("http") else "https://www." + url
    
    print(f"\n{'='*50}")
    print(f"Processing article: {article_id} - {article_url}")
    print(f"{'='*50}\n")
    
    # Step 1: Extract content
    print(f"[1/3] Extracting content from {article_url}")
    try:
        extracted_content = await extract_main_content(article_url)
        if not extracted_content or extracted_content.startswith("Failed to extract"):
            print(f"Warning: Extraction issue for {article_url}")
        else:
            print(f"Successfully extracted {len(extracted_content)} characters")
    except Exception as e:
        print(f"[ERROR] Failed to extract content: {e}")
        extracted_content = f"Extraction error: {str(e)}"
    
    # Step 2: Clean and structure content
    print(f"[2/3] Cleaning and structuring content for article {article_id}")
    try:
        # Process with LLM
        processed_article = extract_content_with_llm(extracted_content)
        
        # Analyze content type
        content_analysis = analyze_content_type(processed_article)
        processed_article["content_type"] = content_analysis["content_type"]
        processed_article["type_confidence"] = content_analysis["confidence"]
        processed_article["type_reasoning"] = content_analysis["reasoning"]
        
        # Add original article metadata
        processed_article["article_id"] = article_id
        processed_article["original_url"] = article_url
        
        # Print summary of what was extracted
        print(f"Processed article {article_id}:")
        print(f"  Title: {processed_article['title'][:70]}..." if len(processed_article['title']) > 70 else f"  Title: {processed_article['title']}")
        print(f"  Date: {processed_article['publication_date']}")
        print(f"  Author: {processed_article['author']}")
        print(f"  Content length: {len(processed_article['main_content'])} chars")
        print(f"  Content type: {processed_article['content_type']} (confidence: {processed_article['type_confidence']:.2f})")
    except Exception as e:
        print(f"[ERROR] Failed to clean content: {e}")
        processed_article = {
            "title": "",
            "publication_date": "",
            "author": "",
            "main_content": extracted_content,
            "content_type": "error",
            "type_confidence": 0.0,
            "type_reasoning": f"Error during cleaning: {str(e)}",
            "article_id": article_id,
            "original_url": article_url
        }
    
    # Step 3: Update the database with processed content (unless in debug mode)
    print(f"[3/3] {'Preparing data for' if debug else 'Updating'} database for article {article_id}")
    
    update_data = {
        "contentType": processed_article["content_type"],
        "content": processed_article["main_content"],
        "author": processed_article["author"],
        "isProcessed": True
    }
    
    if debug:
        print("\n===== DEBUG MODE: SKIPPING DATABASE UPDATE =====")
        print("Data that would be updated:")
        for key, value in update_data.items():
            if key == "content":
                print(f"  {key}: {value[:100]}..." if len(value) > 100 else f"  {key}: {value}")
            else:
                print(f"  {key}: {value}")
        print("=============================================\n")
    else:
        try:
            response = supabase_client.table("TeamSourceArticles").update(update_data).eq("id", article_id).execute()
            
            if response.data:
                print(f"Successfully updated article {article_id} in database")
            else:
                print(f"No rows updated for article {article_id}")
        except Exception as e:
            print(f"[ERROR] Failed to update database: {e}")
    
    return processed_article

async def main(debug: bool = DEBUG):
    try:
        if debug:
            print("\n****************************************")
            print("* RUNNING IN DEBUG MODE                *")
            print("* Database updates will be skipped     *")
            print("****************************************\n")
            
        # Step 1: Get unprocessed articles
        print("Fetching unprocessed articles...")
        unprocessed_articles = get_unprocessed_team_articles()
        if not unprocessed_articles:
            print("No unprocessed articles found.")
            return
            
        print(f"Found {len(unprocessed_articles)} unprocessed articles.")
        
        # Step 2: Process each article through the entire pipeline
        processed_count = 0
        
        for i, article in enumerate(unprocessed_articles):
            print(f"\nProcessing article {i+1}/{len(unprocessed_articles)}")
            
            # Process this article through extraction, cleaning, and database update
            processed_article = await process_article(article, debug=debug)
            processed_count += 1
            
            # Add a small delay between processing articles to avoid rate limiting
            if i < len(unprocessed_articles) - 1:
                print("\nPausing briefly before processing next article...")
                await asyncio.sleep(2)
        
        print("\nPipeline complete!")
        print(f"Processed {processed_count} articles{' (in debug mode)' if debug else ''}.")
        
    except Exception as e:
        print(f"Error in processing pipeline: {e}")
        import traceback
        print(f"Exception traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    # Check for command line arguments to enable debug mode
    if len(sys.argv) > 1 and sys.argv[1].lower() in ["--debug", "-d"]:
        debug_mode = True
    else:
        debug_mode = DEBUG
        
    asyncio.run(main(debug=debug_mode))
