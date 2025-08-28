#!/usr/bin/env python3
"""
This script reads the extracted content from JSON and uses GPT-5 family models to
extract and structure the content into a clean format.

Process:
1. Loads the extracted content from a JSON file.
2. Cleans the text by removing unnecessary elements.
3. Uses the LLM to extract structured information such as title, publication date, author, and main content.
4. Analyzes the content type.
5. Cleans the publication date to a PostgreSQL-compatible format.
6. Processes all articles and saves the cleaned content to a new JSON file.
7. Updates the article content type in the database if necessary.
"""

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
from pathlib import Path

# Add src directory to Python path to allow importing project modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.core.utils.LLM_init import initialize_llm_client, ModelType
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase_client: Optional[Client] = None

# Check if running in CI environment and set a flag
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

# =========================
# LLM CLIENT INITIALIZATION
# =========================
# Extraction: gpt-5-nano (fast/cheap)
# Classification: gpt-5-mini (strong enough for this task)
extract_client, extract_model = initialize_llm_client(model_type="gpt-5-nano")
classify_client, classify_model = initialize_llm_client(model_type="gpt-5-mini")


def load_extracted_content(file_path: str) -> Dict[str, Any]:
    """
    Load the extracted content from a JSON file.
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
    Removes image descriptions, extra backslashes, and links (keeps visible text),
    and collapses whitespace.
    """
    if not text:
        return ""
    # Remove image descriptions ![...](...)
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', text)
    # Remove extra backslashes
    text = text.replace('\\\\', '\\').replace('\\"', '"')
    # Remove markdown links but keep anchor text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove simple HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def clean_publication_date(date_string: str) -> Optional[str]:
    """
    Convert publication date to PostgreSQL timestamptz format (ISO 8601).
    """
    if not date_string:
        return None
    try:
        parsed_date = parser.parse(date_string, fuzzy=True)
        formatted_date = parsed_date.isoformat()
        return formatted_date
    except Exception as e:
        logging.error(f"Error parsing date '{date_string}': {e}")
        return None


def num_tokens(text: str, model: str) -> int:
    """
    Return the number of tokens in ``text`` for ``model``.
    """
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def chunk_text(text: str, max_tokens: int, model: str) -> List[str]:
    """
    Split ``text`` into chunks each with at most ``max_tokens`` tokens.
    """
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)
    chunks = [enc.decode(tokens[i:i + max_tokens]) for i in range(0, len(tokens), max_tokens)]
    return chunks


def extract_content_with_llm(content: str) -> Dict[str, str]:
    """
    Extract article content using the configured LLM:
    - Try gpt-5-nano first (fast/cheap)
    - Escalate to gpt-5-mini if results look weak (empty title + short content, or bad date parse)
    Uses JSON-only responses and chunks long inputs.
    """
    def _run_extraction(client, model, cleaned_content: str, chunk_size: int) -> List[Dict[str, str]]:
        chunks = chunk_text(cleaned_content, chunk_size, model)
        out: List[Dict[str, str]] = []
        for idx, chunk in enumerate(chunks):
            if idx == 0:
                prompt = f"""You are a content extraction assistant. Given the article content below, extract these fields and return ONLY a valid JSON object:

- title (string; "" if not found)
- publication_date (string; keep original format, "" if not found)
- author (string; keep as written, "" if not found)
- main_content (string; remove nav/ads)

Example:
{{
  "title": "Example Article Title",
  "publication_date": "Mar 14, 2025",
  "author": "John Doe",
  "main_content": "The main article text..."
}}

Article content:
{chunk}"""
            else:
                prompt = f"""Continue extracting ONLY the remaining main article text from the chunk below.
Return a JSON object with only this key:
{{ "main_content": "..." }}

Text:
{chunk}"""

            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a content extraction assistant. Respond with a single JSON object only."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            text = (resp.choices[0].message.content or "").strip()
            out.append(json.loads(text))
        return out

    cleaned_content = clean_text(content)

    max_tokens = int(os.getenv("LLM_MAX_TOKENS", "16000"))
    # Keep headroom; output is small because we force JSON
    chunk_size = max_tokens - 2000

    # 1) Try gpt-5-nano (globals: extract_client/extract_model)
    try:
        results = _run_extraction(extract_client, extract_model, cleaned_content, chunk_size)
    except Exception as e:
        print(f"Error processing with LLM (nano): {e}")
        # If nano call fails hard, fall back to returning cleaned content as-is
        return {
            "title": "",
            "publication_date": "",
            "author": "",
            "main_content": cleaned_content,
        }

    # Build fields
    title = results[0].get("title", "") if results else ""
    publication_date = results[0].get("publication_date", "") if results else ""
    author = results[0].get("author", "") if results else ""
    main_content = " ".join(r.get("main_content", "") for r in results)

    # 2) Decide whether to escalate to gpt-5-mini (stronger)
    escalate = False
    if not title and len(main_content) < 500:
        escalate = True
    elif publication_date and not clean_publication_date(publication_date):
        escalate = True

    if escalate:
        print("⚠️ Escalating extraction to gpt-5-mini...")
        try:
            # Reuse your already-initialized mini client if available:
            # classify_client/classify_model are gpt-5-mini in your setup.
            mini_client, mini_model = classify_client, classify_model
            # If you prefer to initialize fresh:
            # mini_client, mini_model = initialize_llm_client(model_type="gpt-5-mini")
            results2 = _run_extraction(mini_client, mini_model, cleaned_content, chunk_size)

            # Rebuild fields only if we actually improved something
            title2 = results2[0].get("title", "") if results2 else title
            pub2 = results2[0].get("publication_date", "") if results2 else publication_date
            author2 = results2[0].get("author", "") if results2 else author
            main2 = " ".join(r.get("main_content", "") for r in results2) or main_content

            # Adopt escalated values
            title, publication_date, author, main_content = title2, pub2, author2, main2
        except Exception as e:
            print(f"Escalation to gpt-5-mini failed: {e}")

    return {
        "title": title,
        "publication_date": publication_date,
        "author": author,
        "main_content": main_content,
    }


def analyze_content_type(content: Dict[str, str]) -> Dict[str, Any]:
    """
    Analyze the content and determine its category using GPT-5-mini, with escalation to GPT-5 on low confidence.
    Returns: content_type, confidence (0..1), reasoning.
    Allowed types: ["news_article","topic_collection","news_collection","empty_content","news-round-up","wrong_content"]
    """
    def _strip_html_and_ws(s: str, limit: int) -> str:
        if not s:
            return ""
        s = re.sub(r"<[^>]+>", " ", s)   # crude HTML strip
        s = re.sub(r"\s+", " ", s).strip()
        return s[:limit]

    def _coerce_conf(x: Any) -> float:
        try:
            v = float(x)
        except Exception:
            return 0.0
        if v != v:  # NaN
            return 0.0
        return max(0.0, min(1.0, v))

    def _run_classification(client, model, prompt: str) -> Dict[str, Any]:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a content analysis assistant. Respond with a single JSON object only."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        text = (resp.choices[0].message.content or "").strip()
        res = json.loads(text)

        valid_types = {"news_article", "topic_collection", "news_collection", "empty_content", "news-round-up", "wrong_content"}
        ctype = str(res.get("content_type", "")).strip()
        if ctype not in valid_types:
            raise ValueError(f"Invalid content type. Must be one of {sorted(valid_types)}")
        conf = _coerce_conf(res.get("confidence"))
        reasoning = str(res.get("reasoning") or "").strip()

        # If model is unsure but claims empty/wrong, avoid too-low confidence (common noise)
        if ctype in {"empty_content", "wrong_content"} and conf < 0.5:
            conf = 0.5

        return {"content_type": ctype, "confidence": conf, "reasoning": reasoning or "Model classification"}

    # 1) Heuristic: roundup by URL (broader & case-insensitive)
    url = (content.get("url") or "").lower()
    if re.search(r"(?:^|/)(?:nfl[-_/]?news[-_/]?round[-_]?up|news[-_/]?round[-_]?up)(?:/|$)", url):
        return {"content_type": "news-round-up", "confidence": 1.0, "reasoning": "URL matches roundup pattern"}

    # 2) Prepare compact, clean text
    title = _strip_html_and_ws(content.get("title", ""), 200)
    main_content = _strip_html_and_ws(content.get("main_content", ""), 1000)

    # If nothing to classify, short-circuit
    if not (title or main_content):
        return {"content_type": "empty_content", "confidence": 1.0, "reasoning": "No title or content"}

    # 3) Build prompt
    content_summary = f"Title: {title}\n\nContent excerpt: {main_content}"
    prompt = f"""Classify the content. Return ONLY a JSON object with keys:
- content_type: one of ["news_article","topic_collection","news_collection","empty_content","news-round-up","wrong_content"]
- confidence: 0..1
- reasoning: short explanation

Rules:
- news_article: single coherent NFL story about one specific news item.
- topic_collection: multiple related NFL snippets about the same topic.
- news_collection: multiple unrelated NFL topics.
- news-round-up: a roundup format with short NFL updates.
- empty_content: too short or no meaningful information.
- wrong_content: not about NFL American Football.

Content:
{content_summary}"""

    # 4) First pass: gpt-5-mini (globals: classify_client/classify_model)
    try:
        result = _run_classification(classify_client, classify_model, prompt)
    except Exception as e:
        print(f"Error analyzing content type (mini): {e}")
        # Try a direct escalation to full gpt-5 when mini fails hard
        try:
            print("⚠️ Escalating classification to gpt-5 due to error...")
            gpt5_client, gpt5_model = initialize_llm_client(model_type="gpt-5")
            return _run_classification(gpt5_client, gpt5_model, prompt)
        except Exception as e2:
            print(f"Escalation to gpt-5 failed: {e2}")
            return {
                "content_type": "empty_content",
                "confidence": 0.2,
                "reasoning": f"Error during analysis: {str(e)}; escalation failed: {str(e2)}"
            }

    # 5) Decide whether to escalate based on confidence / uncertainty
    conf = result["confidence"]
    ctype = result["content_type"]
    escalate = (conf < 0.65) or (ctype in {"empty_content", "wrong_content"} and conf < 0.6)

    if escalate:
        print("⚠️ Escalating classification to gpt-5 (low confidence/uncertain)...")
        try:
            gpt5_client, gpt5_model = initialize_llm_client(model_type="gpt-5")
            result2 = _run_classification(gpt5_client, gpt5_model, prompt)
            return result2
        except Exception as e:
            print(f"Escalation to gpt-5 failed: {e}")
            # Fall back to the mini result rather than erroring out
            return result

    return result

def process_all_articles(extracted_data: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """
    Process all articles in the extracted data using LLM.
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
            content_with_url = {
                **processed_article,
                "url": content_data.get("url", "") if isinstance(content_data, dict) else ""
            }
            content_analysis = analyze_content_type(content_with_url)
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
    if len(sys.argv) > 1 and sys.argv[1] == "--update-content-types":
        update_existing_articles_content_type()
    else:
        main()
