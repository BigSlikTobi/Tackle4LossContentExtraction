"""
Batched cleanup pipeline for processing articles in smaller chunks.
This version processes articles in configurable batches to prevent CPU overload.
It's designed to handle large numbers of unprocessed articles by processing them
in smaller, manageable chunks with optional delays between batches.
"""
import asyncio
import sys
import os
import time
import traceback 
import argparse
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
    from src.core.db.fetch_unprocessed_articles import get_unprocessed_articles_batch, count_unprocessed_articles
    from src.core.utils.lock_manager import acquire_lock, release_lock
    from src.modules.processing.article_processor import process_article
else:
    # In local environment, imports are relative to src directory
    try:
        from core.db.fetch_unprocessed_articles import get_unprocessed_articles_batch, count_unprocessed_articles
        from core.utils.lock_manager import acquire_lock, release_lock
        from modules.processing.article_processor import process_article
    except ImportError:
        # Fallback to src. prefix if relative imports fail
        from src.core.db.fetch_unprocessed_articles import get_unprocessed_articles_batch, count_unprocessed_articles
        from src.core.utils.lock_manager import acquire_lock, release_lock
        from src.modules.processing.article_processor import process_article


async def process_article_batch(batch_articles: List[Dict], batch_num: int, total_batches: int) -> tuple[int, int]:
    """
    Process a batch of articles.
    
    Args:
        batch_articles: List of articles to process
        batch_num: Current batch number (for logging)
        total_batches: Total number of batches (for logging)
        
    Returns:
        Tuple of (successful_count, failed_count)
    """
    print(f"\n=== Processing Batch {batch_num}/{total_batches} ({len(batch_articles)} articles) ===")
    
    processing_tasks = []
    
    # Create concurrent tasks for this batch
    for i, article in enumerate(batch_articles):
        print(f"  Scheduling article {i+1}/{len(batch_articles)} for processing (ID: {article.get('id', 'N/A')})")
        task = asyncio.create_task(process_article(article))
        processing_tasks.append(task)
    
    # Wait for all tasks in this batch to complete
    print(f"  Waiting for {len(processing_tasks)} article processing tasks to complete...")
    batch_start_time = time.time()
    
    try:
        results = await asyncio.gather(*processing_tasks, return_exceptions=True)
    except Exception as e:
        print(f"  ERROR: Batch processing failed: {e}")
        return 0, len(batch_articles)
    
    # Count results
    successful_count = 0
    failed_count = 0
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"  ERROR: Article {i+1} failed: {result}")
            failed_count += 1
        elif result is not None:
            successful_count += 1
        else:
            failed_count += 1
    
    batch_end_time = time.time()
    batch_duration = batch_end_time - batch_start_time
    
    print(f"  Batch {batch_num} completed in {batch_duration:.2f} seconds")
    print(f"  Success: {successful_count}, Failed: {failed_count}")
    
    return successful_count, failed_count


async def main():
    parser = argparse.ArgumentParser(description='Batched Cleanup Pipeline')
    parser.add_argument('--batch-size', type=int, default=10, 
                       help='Number of articles to process per batch (default: 10)')
    parser.add_argument('--max-batches', type=int, default=None,
                       help='Maximum number of batches to process (default: no limit)')
    parser.add_argument('--delay', type=int, default=0,
                       help='Delay between batches in seconds (default: 0)')
    parser.add_argument('--concurrent-limit', type=int, default=None,
                       help='Limit concurrent articles per batch (default: same as batch-size)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be processed without actually processing')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.batch_size < 1:
        print("ERROR: Batch size must be at least 1")
        sys.exit(1)
    
    if args.max_batches is not None and args.max_batches < 1:
        print("ERROR: Max batches must be at least 1")
        sys.exit(1)
    
    if args.delay < 0:
        print("ERROR: Delay cannot be negative")
        sys.exit(1)
    
    # Set concurrent limit
    concurrent_limit = args.concurrent_limit or args.batch_size
    
    # Attempt to acquire the lock
    if not args.dry_run and not acquire_lock():
        print("Pipeline is already running. Exiting.")
        sys.exit(0)

    pipeline_start_time = time.time()
    print("=== Starting Batched Processing Pipeline ===")
    print(f"Configuration:")
    print(f"  - Batch size: {args.batch_size} articles")
    print(f"  - Max batches: {args.max_batches or 'unlimited'}")
    print(f"  - Delay between batches: {args.delay} seconds")
    print(f"  - Concurrent limit per batch: {concurrent_limit}")
    print(f"  - Dry run: {args.dry_run}")
    
    try:
        # Get total count of unprocessed articles
        print("\nCounting unprocessed articles...")
        total_unprocessed = count_unprocessed_articles()
        print(f"Total unprocessed articles: {total_unprocessed}")
        
        if total_unprocessed == 0:
            print("No unprocessed articles found. Exiting.")
            return
        
        # Calculate number of batches needed
        total_batches = (total_unprocessed + args.batch_size - 1) // args.batch_size  # Ceiling division
        if args.max_batches:
            total_batches = min(total_batches, args.max_batches)
            articles_to_process = min(total_unprocessed, args.max_batches * args.batch_size)
        else:
            articles_to_process = total_unprocessed
        
        print(f"Will process {articles_to_process} articles in {total_batches} batches")
        
        if args.dry_run:
            print("\n=== DRY RUN - No articles will be processed ===")
            for batch_num in range(1, total_batches + 1):
                offset = (batch_num - 1) * args.batch_size
                print(f"Batch {batch_num}: Would process {args.batch_size} articles starting from offset {offset}")
            return
        
        # Process batches
        total_successful = 0
        total_failed = 0
        
        for batch_num in range(1, total_batches + 1):
            # Calculate offset for this batch
            offset = (batch_num - 1) * args.batch_size
            
            # Fetch articles for this batch
            print(f"\nFetching batch {batch_num}/{total_batches} (offset: {offset})...")
            batch_articles = get_unprocessed_articles_batch(limit=args.batch_size, offset=offset)
            
            if not batch_articles:
                print(f"No articles found for batch {batch_num}. Stopping.")
                break
            
            # Process this batch
            successful, failed = await process_article_batch(batch_articles, batch_num, total_batches)
            total_successful += successful
            total_failed += failed
            
            # Delay before next batch (if not the last batch)
            if batch_num < total_batches and args.delay > 0:
                print(f"  Waiting {args.delay} seconds before next batch...")
                await asyncio.sleep(args.delay)
        
        # Final summary
        pipeline_end_time = time.time()
        total_duration = pipeline_end_time - pipeline_start_time
        
        print(f"\n=== Batched Processing Pipeline Complete ===")
        print(f"Total processing time: {total_duration:.2f} seconds")
        print(f"Batches processed: {batch_num}")
        print(f"Total articles processed: {total_successful + total_failed}")
        print(f"Successfully processed: {total_successful}")
        print(f"Failed: {total_failed}")
        
        if total_failed > 0:
            success_rate = (total_successful / (total_successful + total_failed)) * 100
            print(f"Success rate: {success_rate:.1f}%")

    except KeyboardInterrupt:
        print("\n\nPipeline interrupted by user (Ctrl+C)")
        sys.exit(130)
    except Exception as e:
        print(f"[FATAL ERROR] Unhandled exception in batched pipeline: {e}")
        print(traceback.format_exc())
        sys.exit(1)
    finally:
        if not args.dry_run:
            release_lock()
            print("--- Lock released. Pipeline shutdown complete. ---")


if __name__ == "__main__":
    asyncio.run(main())
