"""
This script is the main pipeline for processing unprocessed articles.
For each article:
1. Fetch unprocessed articles from the database
2. Extract the main content from each article
3. Clean and structure the content
4. Create and store embeddings
5. Update the database with processed content
6. Check for similar articles and update duplications
7. Cluster recent articles based on content similarity
"""
import asyncio
import sys
import os
import time
import traceback  # Import traceback for detailed error logging
from datetime import datetime, timedelta, UTC
from typing import Dict, Any, List, Set, Optional

# Add the parent directory to the Python path to allow for absolute imports
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Simpler approach assuming structure:
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# Import the necessary modules
from fetchUnprocessedArticles import get_unprocessed_articles, supabase_client
from extractContent import extract_main_content
from cleanContent import extract_content_with_llm, analyze_content_type
from LLM_init import initialize_llm_client
from create_embeddings import create_and_store_embedding
from find_similar_articles import (
    fetch_recent_embeddings, # Renamed in find_similar_articles.py
    find_similar_articles,
    print_similar_articles,
    # fetch_article_details, # Not directly used here anymore
    # update_duplicate_articles # Handled within print_similar_articles now
)
# Import the clustering function
from cluster_articles import run_clustering_pipeline

# Initialize the LLM client from the shared module
# Assuming LLM_init handles potential errors during initialization
try:
    client, _ = initialize_llm_client() # Use tuple unpacking if needed elsewhere
except ValueError as e:
    print(f"FATAL: Failed to initialize LLM Client: {e}")
    sys.exit(1) # Exit if LLM can't be initialized

# --- Helper function to fetch embeddings (modified for find_similar_articles logic) ---
# Note: find_similar_articles.py now has fetch_recent_embeddings.
# We might need a different function here if we want *just* the newly processed ones for some reason
# but fetch_recent_embeddings (last 48h) seems appropriate for the similarity check.


async def process_article(article: Dict[str, Any]) -> Optional[int]:
    """
    Process a single article through extraction, cleaning, embedding, and DB update.

    Args:
        article: Dictionary containing article information

    Returns:
        The article ID if processed successfully, None otherwise.
    """
    article_id = article["id"]
    # Normalize URL: use article["url"] if it starts with http; otherwise, prepend "https://www."
    url = article["url"]
    # Ensure URL is not None or empty before processing
    if not url:
        print(f"[ERROR] Skipping article {article_id} due to missing URL.")
        return None
    article_url = url if url.startswith("http") else "https://www." + url

    print(f"\n{'='*50}")
    print(f"Processing article: {article_id} - {article_url}")
    print(f"{'='*50}\n")

    processed_data = None # To hold structured data for embedding/update

    # Step 1: Extract content
    print(f"[1/4] Extracting content from {article_url}")
    try:
        extracted_content = await extract_main_content(article_url)
        if not extracted_content or extracted_content.startswith("Failed to extract") or extracted_content.startswith("Extraction error:") :
            print(f"Warning: Extraction issue for article {article_id}. Content: '{extracted_content[:100]}...'")
            # Decide if we should stop or try to proceed with potentially bad content
            # For now, let's attempt cleaning even with errors, but mark as unprocessed later if needed
        else:
            print(f"Successfully extracted {len(extracted_content)} characters")
    except Exception as e:
        print(f"[ERROR] Failed to extract content for article {article_id}: {e}")
        print(traceback.format_exc())
        extracted_content = f"Extraction error: {str(e)}" # Store error

    # Step 2: Clean and structure content
    print(f"[2/4] Cleaning and structuring content for article {article_id}")
    try:
        # Process with LLM
        # Ensure extracted_content is not None before passing
        if extracted_content is None:
             raise ValueError("Cannot clean None content.")

        processed_article = extract_content_with_llm(extracted_content)

        # Analyze content type only if main_content exists
        if processed_article.get("main_content"):
            content_analysis = analyze_content_type(processed_article)
            processed_article["content_type"] = content_analysis["content_type"]
            processed_article["type_confidence"] = content_analysis["confidence"]
            processed_article["type_reasoning"] = content_analysis["reasoning"]
        else:
            print(f"Warning: No main content found after cleaning for article {article_id}. Setting type to 'empty'.")
            processed_article["content_type"] = "empty_content"
            processed_article["type_confidence"] = 1.0
            processed_article["type_reasoning"] = "No main content extracted or cleaned."

        # Add original article metadata back if needed downstream, although not strictly necessary for DB update
        processed_article["article_id"] = article_id
        # processed_article["original_url"] = article_url # Not stored in DB currently

        # Print summary
        print(f"Cleaned article {article_id}:")
        print(f"  Title: {processed_article.get('title', 'N/A')[:70]}...")
        print(f"  Date: {processed_article.get('publication_date', 'N/A')}")
        print(f"  Author: {processed_article.get('author', 'N/A')}")
        print(f"  Content length: {len(processed_article.get('main_content', ''))} chars")
        print(f"  Content type: {processed_article.get('content_type', 'N/A')} (confidence: {processed_article.get('type_confidence', 0.0):.2f})")

        processed_data = processed_article # Store for next steps

    except Exception as e:
        print(f"[ERROR] Failed to clean content for article {article_id}: {e}")
        print(traceback.format_exc())
        # Prepare minimal data to mark as processed_with_error maybe? Or just skip update?
        # Let's skip DB update and embedding if cleaning fails
        processed_data = None


    # Proceed only if cleaning was successful and we have content
    if processed_data and processed_data.get("main_content"):
        # Step 3: Update the database with processed content
        print(f"[3/4] Updating database for article {article_id}")
        db_update_successful = False
        try:
            update_data = {
                "contentType": processed_data["content_type"],
                "Content": processed_data["main_content"], # Assuming 'Content' is the correct column name
                "Author": processed_data["author"], # Assuming 'Author' is correct
                # Add Title if you have a column for it
                # "Title": processed_data["title"],
                "isProcessed": True # Mark as processed
            }
            # Add publication date if you have a column and it was parsed
            # if processed_data.get("cleaned_date_timestamptz"):
            #    update_data["PublicationDate"] = processed_data["cleaned_date_timestamptz"]


            response = supabase_client.table("SourceArticles").update(update_data).eq("id", article_id).execute()

            # Basic check: Does response indicate success? Needs refinement based on supabase-py v2+
            if response.data: # Check if data is returned, often indicates success
                print(f"Successfully updated article {article_id} in database")
                db_update_successful = True
            else:
                # This might happen if the row doesn't exist or filter doesn't match
                print(f"Warning: Database update for article {article_id} did not return data. Check if article exists or if update conditions matched.")
                # Consider logging response.error if available

        except Exception as e:
            print(f"[ERROR] Failed to update database for article {article_id}: {e}")
            print(traceback.format_exc())

        # Step 4: Create and store embedding *only* if DB update was successful
        if db_update_successful:
            print(f"[4/4] Creating and storing embedding for article {article_id}")
            try:
                # Use asyncio.to_thread to run the synchronous embedding function
                await asyncio.to_thread(
                    create_and_store_embedding,
                    article_id,
                    processed_data["main_content"] # Use the cleaned main content
                )
                # Assuming create_and_store_embedding handles its own prints/errors
                return article_id # Return ID on full success
            except Exception as e:
                print(f"[ERROR] Failed to create/store embedding for article {article_id}: {e}")
                print(traceback.format_exc())
        else:
             print(f"Skipping embedding for article {article_id} due to database update failure.")

    else:
        # If cleaning failed or produced no content, mark as processed but maybe with an error flag?
        # Or just leave isProcessed=False? For now, let's just log and return None.
        print(f"Skipping database update and embedding for article {article_id} due to issues in previous steps.")
        # Optionally, update DB to mark as processed with error state if needed:
        # try:
        #     supabase_client.table("SourceArticles").update({"isProcessed": True, "contentType": "processing_error"}).eq("id", article_id).execute()
        # except Exception as db_err:
        #     print(f"[ERROR] Failed to mark article {article_id} with processing error: {db_err}")

    return None # Return None if processing wasn't fully successful


async def main():
    pipeline_start_time = time.time()
    print("--- Starting Main Processing Pipeline ---")
    try:
        # Step 1: Get unprocessed articles
        print("Fetching unprocessed articles...")
        unprocessed_articles = get_unprocessed_articles()

        if not unprocessed_articles:
            print("No unprocessed articles found.")
            # Still run clustering and similarity check on recent items even if no new ones? Optional.
            # For now, let's exit if none are found initially. Add logic later if needed.
            # return
        else:
            print(f"Found {len(unprocessed_articles)} unprocessed articles.")

        # Step 2: Process each article through the pipeline
        processed_article_ids = set()
        processing_tasks = []

        # Create concurrent tasks for processing articles
        for i, article in enumerate(unprocessed_articles):
             print(f"\nScheduling article {i+1}/{len(unprocessed_articles)} for processing (ID: {article.get('id', 'N/A')})")
             task = asyncio.create_task(process_article(article))
             processing_tasks.append(task)
             # Optional: Add a small delay here if needed to stagger starts slightly
             # await asyncio.sleep(0.1)

        # Wait for all processing tasks to complete
        print(f"\nWaiting for {len(processing_tasks)} article processing tasks to complete...")
        results = await asyncio.gather(*processing_tasks)

        # Collect successfully processed IDs
        processed_count = 0
        for result_id in results:
             if result_id is not None:
                 processed_article_ids.add(result_id)
                 processed_count += 1

        print(f"\n--- Article Processing Complete ---")
        print(f"Successfully processed and embedded {processed_count} articles.")
        failed_count = len(unprocessed_articles) - processed_count
        if failed_count > 0:
             print(f"Failed or skipped processing for {failed_count} articles.")


        # Step 3: Check for similarities among recent articles
        # This step uses fetch_recent_embeddings which gets last 48h non-duplicates
        print("\n--- Starting Similarity Check ---")
        try:
            # Fetch embeddings created in the last 48 hours (from find_similar_articles)
            # This automatically focuses on non-duplicate articles
            embeddings = fetch_recent_embeddings() # Fetches last 48h non-duplicates

            if embeddings:
                print(f"Found {len(embeddings)} embeddings from last 48h for similarity check.")
                # Find and print similar pairs (includes DB update for duplicates)
                similar_pairs = find_similar_articles(embeddings)
                print_similar_articles(similar_pairs) # This function now handles DB updates
            else:
                print("No recent embeddings found to check for similarity.")
        except Exception as e:
            print(f"[ERROR] Failed during similarity check: {e}")
            print(traceback.format_exc())


        # Step 4: Run Article Clustering
        print("\n--- Starting Article Clustering ---")
        try:
            # Run the clustering pipeline (defined in cluster_articles.py)
            # This fetches its own data (last 10 days, news_article type, non-duplicates)
            # It handles its own DB updates for cluster_id
            # Run synchronously within the async main function using to_thread
            await asyncio.to_thread(run_clustering_pipeline)
        except Exception as e:
            print(f"[ERROR] Failed during article clustering: {e}")
            print(traceback.format_exc())


        pipeline_end_time = time.time()
        print("\n--- Main Processing Pipeline Finished ---")
        print(f"Total pipeline execution time: {pipeline_end_time - pipeline_start_time:.2f} seconds")

    except Exception as e:
        print(f"[FATAL ERROR] Unhandled exception in main pipeline: {e}")
        print(traceback.format_exc())
        sys.exit(1) # Indicate failure

if __name__ == "__main__":
    # Consider adding nest_asyncio if running in environments like Jupyter/Spyder
    # import nest_asyncio
    # nest_asyncio.apply()
    asyncio.run(main())