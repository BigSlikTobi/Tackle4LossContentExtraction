"""
This script is the main pipeline for processing unprocessed articles.
For each article:
1. Fetch unprocessed articles from the database
2. Extract the main content from each article
3. Clean and structure the content
4. Create and store embeddings
5. Update the database with processed content
"""
import asyncio
import sys
import os
import time
import traceback  # Import traceback for detailed error logging
from datetime import datetime, timedelta, UTC
from typing import Dict, Any, List, Set, Optional

# Import the necessary modules
from Tackle4LossContentExtraction.core.db.fetch_unprocessed_articles import get_unprocessed_articles
# Removed unused imports: extract_main_content, extract_content_with_llm, analyze_content_type, initialize_llm_client, create_and_store_embedding, update_article_in_db
from Tackle4LossContentExtraction.modules.processing.article_processor import process_article # Import the moved function
# Removed similarity and clustering imports

# Removed LLM client initialization as it's not directly used here anymore

# --- Helper function to fetch embeddings (modified for find_similar_articles logic) ---
# Note: find_similar_articles.py now has fetch_recent_embeddings.
# We might need a different function here if we want *just* the newly processed ones for some reason
# but fetch_recent_embeddings (last 48h) seems appropriate for the similarity check.


async def main():
    pipeline_start_time = time.time()
    print("--- Starting Main Processing Pipeline ---")
    try:
        # Step 1: Get unprocessed articles
        print("Fetching unprocessed articles...")
        unprocessed_articles = get_unprocessed_articles()

        if not unprocessed_articles:
            print("No unprocessed articles found.")
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

        # Removed similarity check and clustering steps

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