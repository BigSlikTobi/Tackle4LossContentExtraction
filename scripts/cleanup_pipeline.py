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
import traceback 
from datetime import datetime, timedelta, UTC
from typing import Dict, Any, List, Set, Optional

# Add src directory to Python path
from pathlib import Path
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_path))

# Import modules - check if we're in CI environment with PYTHONPATH set to root
if os.getenv('PYTHONPATH') == '.' or os.getenv('CI') == 'true':
    # In CI environment, imports are relative to project root
    from src.core.db.fetch_unprocessed_articles import get_unprocessed_articles
    from src.core.utils.lock_manager import acquire_lock, release_lock
    from src.modules.processing.article_processor import process_article
else:
    # In local environment, imports are relative to src directory
    try:
        from core.db.fetch_unprocessed_articles import get_unprocessed_articles
        from core.utils.lock_manager import acquire_lock, release_lock
        from modules.processing.article_processor import process_article
    except ImportError:
        # Fallback to src. prefix if relative imports fail
        from src.core.db.fetch_unprocessed_articles import get_unprocessed_articles
        from src.core.utils.lock_manager import acquire_lock, release_lock
        from src.modules.processing.article_processor import process_article 

# Note: find_similar_articles.py now has fetch_recent_embeddings.
# We might need a different function here if we want *just* the newly processed ones for some reason
# but fetch_recent_embeddings (last 48h) seems appropriate for the similarity check.


async def main():
    # Attempt to acquire the lock
    if not acquire_lock():
        print("Pipeline is already running. Exiting.")
        sys.exit(0)

    pipeline_start_time = time.time()
    print("--- Starting Main Processing Pipeline ---")
    try:
        # The main logic of the pipeline
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
    finally:
        release_lock()
        print("--- Lock released. Pipeline shutdown complete. ---")

if __name__ == "__main__":
    asyncio.run(main())