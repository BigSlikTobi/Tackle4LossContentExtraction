"""
Module for processing a single article through extraction, cleaning, embedding, and DB update.
"""
import asyncio
import traceback
from typing import Dict, Any, Optional
from urllib.parse import unquote

# Assuming the top-level directory is in sys.path (handled by Pipeline.py)
from modules.extraction.extractContent import extract_main_content
from modules.extraction.cleanContent import extract_content_with_llm, analyze_content_type
from core.utils.create_embeddings import create_and_store_embedding
from core.db.update_article import update_article_in_db

async def process_article(article: Dict[str, Any]) -> Optional[int]:
    """
    Process a single article through extraction, cleaning, embedding, and DB update.

    Args:
        article (Dict[str, Any]): Dictionary containing article information.

    Returns:
        Optional[int]: The article ID if processed successfully, None otherwise.
    """
    article_id = article["id"]
    # Normalize URL: use article["url"] if it starts with http; otherwise, prepend "https://www."
    url = article["url"]
    # Ensure URL is not None or empty before processing
    if not url:
        print(f"[ERROR] Skipping article {article_id} due to missing URL.")
        return None
    
    # URL decode the URL in case it's been URL-encoded
    url = unquote(url)
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
                "Content": processed_data["main_content"],
                "Author": processed_data["author"],
                # Add Title if you have a column for it
                # "Title": processed_data["title"],
                "isProcessed": True
            }
            # Add publication date if you have a column and it was parsed
            # if processed_data.get("cleaned_date_timestamptz"):
            #    update_data["PublicationDate"] = processed_data["cleaned_date_timestamptz"]

            db_update_successful = update_article_in_db(article_id, update_data)
            if db_update_successful:
                print(f"Successfully updated article {article_id} in database")
            else:
                print(f"Warning: Database update for article {article_id} did not return data. Check if article exists or if update conditions matched.")
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
