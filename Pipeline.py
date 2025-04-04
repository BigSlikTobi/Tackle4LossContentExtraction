"""
This script is the main pipeline for processing unprocessed articles.
For each article:
1. Fetch unprocessed articles from the database
2. Extract the main content from each article
3. Clean and structure the content
4. Create and store embeddings
5. Check for similar articles and update duplications
6. Update the database with processed content
"""
import asyncio
import sys
import os
import time
from datetime import datetime, timedelta, UTC
from typing import Dict, Any, List, Set

# Add the parent directory to the Python path to allow for absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the necessary modules
from fetchUnprocessedArticles import get_unprocessed_articles, supabase_client
from extractContent import extract_main_content
from cleanContent import extract_content_with_llm, analyze_content_type
from LLM_init import initialize_llm_client
from create_embeddings import create_and_store_embedding
from find_similar_articles import (
    find_similar_articles,
    print_similar_articles,
    fetch_article_details,
    update_duplicate_articles
)

# Initialize the LLM client from the shared module
client = initialize_llm_client()

def fetch_latest_embeddings(article_ids: Set[int]) -> List[Dict[str, Any]]:
    """
    Fetch embeddings for newly processed articles and recent articles (within 48 hours).
    
    Args:
        article_ids: Set of article IDs to fetch embeddings for
        
    Returns:
        List of embedding dictionaries
    """
    try:
        # Get articles from the last 48 hours
        cutoff_time = (datetime.now(UTC) - timedelta(hours=48)).isoformat()
        recent_articles = supabase_client.table("SourceArticles") \
            .select("id") \
            .gte("created_at", cutoff_time) \
            .is_("duplication_of", "null") \
            .execute()
            
        if recent_articles.data:
            # Combine newly processed article IDs with recent article IDs
            all_article_ids = set(article_ids) | {article["id"] for article in recent_articles.data}
            
            # Fetch embeddings for all articles
            embeddings_response = supabase_client.table("ArticleVector") \
                .select("id, embedding, SourceArticle") \
                .in_("SourceArticle", list(all_article_ids)) \
                .execute()
                
            if not embeddings_response.data:
                print("No embeddings found for processed and recent articles")
                return []
                
            print(f"Found {len(embeddings_response.data)} embeddings from processed and recent articles")
            return embeddings_response.data
        else:
            # If no recent articles, just get embeddings for processed articles
            embeddings_response = supabase_client.table("ArticleVector") \
                .select("id, embedding, SourceArticle") \
                .in_("SourceArticle", list(article_ids)) \
                .execute()
                
            if not embeddings_response.data:
                print("No embeddings found for processed articles")
                return []
                
            print(f"Found {len(embeddings_response.data)} embeddings for newly processed articles")
            return embeddings_response.data
    except Exception as e:
        print(f"Error fetching embeddings from database: {e}")
        return []

async def process_article(article: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a single article through the entire pipeline:
    1. Extract content
    2. Clean and structure content
    3. Update the database
    
    Args:
        article: Dictionary containing article information
        
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
    
    # Step 3: Update the database with processed content
    print(f"[3/3] Updating database for article {article_id}")
    try:
        update_data = {
            "contentType": processed_article["content_type"],
            "Content": processed_article["main_content"],
            "Author": processed_article["author"],
            "isProcessed": True
        }
        
        response = supabase_client.table("SourceArticles").update(update_data).eq("id", article_id).execute()
        
        if response.data:
            print(f"Successfully updated article {article_id} in database")
            # Create and store embedding after successful content processing
            await asyncio.to_thread(create_and_store_embedding, article_id, processed_article["main_content"])
        else:
            print(f"No rows updated for article {article_id}")
    except Exception as e:
        print(f"[ERROR] Failed to update database: {e}")
    
    return processed_article

async def main():
    try:
        # Step 1: Get unprocessed articles
        print("Fetching unprocessed articles...")
        unprocessed_articles = get_unprocessed_articles()
        
        if not unprocessed_articles:
            print("No unprocessed articles found.")
            return
            
        print(f"Found {len(unprocessed_articles)} unprocessed articles.")
        
        # Step 2: Process each article through the pipeline
        processed_count = 0
        processed_article_ids = set()
        
        for i, article in enumerate(unprocessed_articles):
            print(f"\nProcessing article {i+1}/{len(unprocessed_articles)}")
            
            # Process this article through extraction, cleaning, and database update
            processed_article = await process_article(article)
            processed_count += 1
            processed_article_ids.add(article["id"])
            
            # Add a small delay between processing articles to avoid rate limiting
            if i < len(unprocessed_articles) - 1:
                print("\nPausing briefly before processing next article...")
                await asyncio.sleep(2)
        
        # Step 3: Check for similarities in newly processed articles
        if processed_article_ids:
            print("\nChecking for similar articles...")
            embeddings = fetch_latest_embeddings(processed_article_ids)
            
            if embeddings:
                similar_pairs = find_similar_articles(embeddings)
                print_similar_articles(similar_pairs)
        
        print("\nPipeline complete!")
        print(f"Processed {processed_count} articles.")
        
    except Exception as e:
        print(f"Error in processing pipeline: {e}")
        import traceback
        print(f"Exception traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(main())
