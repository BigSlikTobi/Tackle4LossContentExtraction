#!/usr/bin/env python3
"""
End-to-end pipeline:

1) Fetch unprocessed articles from DB
2) Crawl & LLM-extract main content with Crawl4AI (writes extracted_contents.json)
3) If a page is too short, enrich via AMP / JSON-LD / Readability (non-invasive fallback)
4) Extract structured fields (title/date/author/main) with gpt-5-nano; escalate to gpt-5-mini if weak
5) Classify content type with gpt-5-mini; escalate to gpt-5 if low-confidence
6) Normalize date
7) Save cleaned_contents.json (and optional DB updates)

Notes:
- Crawl4AI flow is preserved (AsyncWebCrawler + LLMExtractionStrategy).
- JSON-only responses from OpenAI to avoid brace scraping.
"""

import os
import sys
import re
import json
import time
import random
import asyncio
import logging
from pathlib import Path

# Add project root to Python path to allow importing project modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
import tiktoken

# Optional readability support (pip install readability-lxml)
try:
    from readability import Document
    _HAS_READABILITY = True
except Exception:
    _HAS_READABILITY = False

# Crawl4AI
from crawl4ai import AsyncWebCrawler, CacheMode
from crawl4ai.extraction_strategy import LLMExtractionStrategy

# Project imports
try:
    # Try relative imports first (when run from project root)
    from core.db.fetch_unprocessed_articles import get_unprocessed_articles
    from core.utils.LLM_init import initialize_llm_client
except ImportError:
    # Fallback to src. prefix if relative imports fail
    from src.core.db.fetch_unprocessed_articles import get_unprocessed_articles
    from src.core.utils.LLM_init import initialize_llm_client

from supabase import create_client, Client
from dotenv import load_dotenv


# ------------------
# Environment / DB
# ------------------
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
IS_CI = os.getenv("CI") == 'true' or os.getenv("GITHUB_ACTIONS") == 'true'

supabase_client: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY and not IS_CI:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"WARNING: Failed to initialize Supabase client: {e}")
elif IS_CI and SUPABASE_URL and SUPABASE_KEY and not SUPABASE_KEY.startswith('test-'):
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"WARNING: Failed to initialize Supabase client in CI: {e}")
elif not IS_CI and (not SUPABASE_URL or not SUPABASE_KEY):
    print("ERROR: SUPABASE_URL and/or SUPABASE_KEY environment variables are not set.")
    sys.exit(1)
else:
    print("WARNING: Supabase credentials not available or in CI mode. Running without database access.")

# ------------------
# LLM clients
# ------------------
# Extraction (OpenAI): nano → escalate to mini
extract_client, extract_model = initialize_llm_client("gpt-5-nano")
classify_client, classify_model = initialize_llm_client("gpt-5-mini")
# full gpt-5 is initialized on-demand for classification escalation


# -------------
# Text helpers
# -------------
def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', text)        # markdown images
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)     # keep link text, drop href
    text = re.sub(r"<[^>]+>", " ", text)                     # strip HTML tags
    text = text.replace('\\\\', '\\').replace('\\"', '"')    # normalize slashes/quotes
    text = re.sub(r'\s+', ' ', text).strip()                 # collapse whitespace
    return text

def clean_publication_date(date_string: str) -> Optional[str]:
    if not date_string:
        return None
    try:
        return date_parser.parse(date_string, fuzzy=True).isoformat()
    except Exception as e:
        logging.error(f"Error parsing date '{date_string}': {e}")
        return None

def num_tokens(text: str, model: str) -> int:
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))

def chunk_text(text: str, max_tokens: int, model: str) -> List[str]:
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    toks = enc.encode(text)
    return [enc.decode(toks[i:i+max_tokens]) for i in range(0, len(toks), max_tokens)]

# -----------------------------
# Post-Crawl enrichment helpers
# -----------------------------
def _http_get(url: str, timeout: int = 15) -> Optional[str]:
    try:
        headers = {
            "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
                           " AppleWebKit/537.36 (KHTML, like Gecko)"
                           " Chrome/119.0 Safari/537.36"),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://www.google.com/",
        }
        r = requests.get(url, headers=headers, timeout=timeout)
        if 200 <= r.status_code < 300:
            return r.text
    except Exception as e:
        print(f"_http_get error for {url}: {e}")
    return None

def _try_amp_url(html: str, base_url: str) -> Optional[str]:
    try:
        soup = BeautifulSoup(html, "html.parser")
        amp = soup.find("link", rel=lambda v: v and "amphtml" in v.lower())
        if amp and amp.get("href"):
            amp_url = amp["href"]
            if amp_url.startswith("//"):
                amp_url = "https:" + amp_url
            elif amp_url.startswith("/"):
                from urllib.parse import urljoin
                amp_url = urljoin(base_url, amp_url)
            amp_html = _http_get(amp_url)
            if amp_html and len(amp_html) > 1000:
                return amp_html
    except Exception as e:
        print(f"_try_amp_url failed: {e}")
    return None

def _extract_ld_json_article_body(html: str) -> Dict[str, str]:
    out = {"title": "", "author": "", "publication_date": "", "main_content": ""}
    try:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string or "")
            except Exception:
                continue
            nodes = data if isinstance(data, list) else [data]
            for node in nodes:
                t = node.get("@type")
                if isinstance(t, list):
                    is_article = any(isinstance(x, str) and x.lower().endswith("article") for x in t)
                else:
                    is_article = isinstance(t, str) and t.lower().endswith("article")
                if not is_article:
                    continue
                out["title"] = out["title"] or node.get("headline", "")
                author = node.get("author")
                if isinstance(author, dict):
                    out["author"] = out["author"] or author.get("name", "")
                elif isinstance(author, list) and author:
                    if isinstance(author[0], dict):
                        out["author"] = out["author"] or author[0].get("name", "")
                    elif isinstance(author[0], str):
                        out["author"] = out["author"] or author[0]
                out["publication_date"] = out["publication_date"] or node.get("datePublished", "") or node.get("dateCreated", "")
                body = node.get("articleBody") or node.get("description") or ""
                if body and len(body) > len(out["main_content"]):
                    out["main_content"] = body
    except Exception as e:
        print(f"_extract_ld_json_article_body failed: {e}")
    return out

def _readability_extract(html: str) -> str:
    if not _HAS_READABILITY:
        return ""
    try:
        doc = Document(html)
        summary_html = doc.summary(html_partial=True)
        soup = BeautifulSoup(summary_html, "html.parser")
        return soup.get_text(separator=" ", strip=True)
    except Exception as e:
        print(f"_readability_extract failed: {e}")
        return ""

def enrich_content_from_url_if_needed(original_content: str, url: str) -> str:
    """
    If Crawl4AI yields very short text, try AMP, JSON-LD, and Readability.
    Only replace if we find a meaningfully longer body.
    """
    content = original_content or ""
    if len(content) >= 800 or not url:
        return content

    html = _http_get(url)
    if not html:
        return content

    amp_html = _try_amp_url(html, url)
    if amp_html:
        html = amp_html

    best = content
    ld = _extract_ld_json_article_body(html)
    if ld.get("main_content") and len(ld["main_content"]) > len(best):
        best = ld["main_content"]

    readab = _readability_extract(html)
    if readab and len(readab) > len(best):
        best = readab

    if len(best) > max(len(content), 400):
        print(f"[ENRICH] Replacing short Crawl4AI content using AMP/LD/Readability for: {url}")
        return best
    return content


# -----------------------------------
# Crawl4AI: extract_main_content step
# -----------------------------------
# Use the same OpenAI key for Crawl4AI LLM strategy
_OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

async def extract_main_content(full_url: str) -> str:
    """
    Extract the main content via Crawl4AI + LLMExtractionStrategy (unchanged behavior).
    Returns a string (possibly JSON-ish blocks depending on strategy), or an error message.
    """
    try:
        async with AsyncWebCrawler(verbose=False) as crawler:
            llm_strategy = LLMExtractionStrategy(
                llm_config={
                    "provider": f"openai/{extract_model}",   # e.g., openai/gpt-5-nano
                    "api_token": _OPENAI_API_KEY,
                },
                verbose=True,
                word_count_threshold=50,
                exclude_tags=["footer", "header", "nav", "aside", "script", "style", "img"],
                exclude_external_links=True,
                timeout=40,
                instructions="""
                    You are a content extractor. Extract the relevant article text blocks
                    and return them as plain text with minimal noise.
                    Exclude navigation, ads, and boilerplate.
                """,
                output_format="text",
                max_retries=3
            )

            max_attempts = 4
            for attempt in range(max_attempts):
                try:
                    if attempt > 0:
                        jitter = random.uniform(0.5, 2.0)
                        wait_time = (2 ** attempt) + jitter
                        print(f"API attempt {attempt+1}/{max_attempts}, waiting {wait_time:.1f} seconds...")
                        await asyncio.sleep(wait_time)

                    print(f"Attempting extraction (try {attempt+1}/{max_attempts})...")
                    result = await crawler.arun(
                        url=full_url,
                        extraction_strategy=llm_strategy,
                        max_pages=1,
                        cache_mode=CacheMode.WRITE_ONLY,
                    )
                    content = result.extracted_content
                    if content and len(content) > 50:
                        return content
                    else:
                        print(f"LLM returned insufficient content on attempt {attempt+1}")
                        if attempt == max_attempts - 1:
                            print("Using best available content after all attempts")
                            return content if content else "No content could be extracted"
                except Exception as e:
                    err = str(e)
                    print(f"API error on attempt {attempt+1}: {err}")
                    if attempt == max_attempts - 1:
                        return f"Failed to extract content after {max_attempts} attempts. Last error: {err}"

            return "Content extraction failed after multiple attempts"

    except Exception as e:
        error_type = type(e).__name__
        error_message = str(e)
        print(f"[ERROR] Outer exception during extraction for {full_url}. Type: {error_type}, Message: {error_message}", file=sys.stderr)
        return f"Extraction failed for {full_url}. Type: {error_type}, Error: {error_message}"

# ----------------------------
# OpenAI extraction (escalation)
# ----------------------------
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
            response_format={"type": "json_object"},
        )
        text = (resp.choices[0].message.content or "").strip()
        out.append(json.loads(text))
    return out

def extract_content_with_llm(article_body: str) -> Dict[str, str]:
    """
    Extract fields using gpt-5-nano → escalate to gpt-5-mini when weak.
    """
    if extract_client is None:  # CI without key
        cleaned = clean_text(article_body)
        return {"title": "", "publication_date": "", "author": "", "main_content": cleaned}

    cleaned_content = clean_text(article_body)
    if len(cleaned_content) < 200:
        return {"title": "", "publication_date": "", "author": "", "main_content": cleaned_content}

    max_tokens = int(os.getenv("LLM_MAX_TOKENS", "16000"))
    chunk_size = max_tokens - 2000

    # 1) nano
    try:
        results = _run_extraction(extract_client, extract_model, cleaned_content, chunk_size)
    except Exception as e:
        print(f"Error processing with LLM (nano): {e}")
        return {"title": "", "publication_date": "", "author": "", "main_content": cleaned_content}

    title = results[0].get("title", "") if results else ""
    publication_date = results[0].get("publication_date", "") if results else ""
    author = results[0].get("author", "") if results else ""
    main_content = " ".join(r.get("main_content", "") for r in results)

    # 2) escalate → mini
    escalate = False
    if not title and len(main_content) < 500:
        escalate = True
    elif publication_date and not clean_publication_date(publication_date):
        escalate = True

    if escalate:
        print("⚠️ Escalating extraction to gpt-5-mini...")
        try:
            mini_client, mini_model = classify_client, classify_model
            results2 = _run_extraction(mini_client, mini_model, cleaned_content, chunk_size)
            title2 = results2[0].get("title", "") if results2 else title
            pub2 = results2[0].get("publication_date", "") if results2 else publication_date
            author2 = results2[0].get("author", "") if results2 else author
            main2 = " ".join(r.get("main_content", "") for r in results2) or main_content
            title, publication_date, author, main_content = title2, pub2, author2, main2
        except Exception as e:
            print(f"Escalation to gpt-5-mini failed: {e}")

    return {"title": title, "publication_date": publication_date, "author": author, "main_content": main_content}

# ------------------------------
# OpenAI classification (escalation)
# ------------------------------
def _strip_html_and_ws(s: str, limit: int) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit]

def _coerce_conf(x: Any) -> float:
    try:
        v = float(x)
    except Exception:
        return 0.0
    if v != v:
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
    data = json.loads(text)

    valid = {"news_article", "topic_collection", "news_collection", "empty_content", "news-round-up", "wrong_content"}
    ctype = str(data.get("content_type", "")).strip()
    if ctype not in valid:
        raise ValueError(f"Invalid content type. Must be one of {sorted(valid)}")
    conf = _coerce_conf(data.get("confidence"))
    reasoning = str(data.get("reasoning") or "").strip()
    if ctype in {"empty_content", "wrong_content"} and conf < 0.5:
        conf = 0.5
    return {"content_type": ctype, "confidence": conf, "reasoning": reasoning or "Model classification"}

def analyze_content_type(content: Dict[str, str]) -> Dict[str, Any]:
    """
    Classify with gpt-5-mini → escalate to gpt-5 if low confidence.
    """
    url = (content.get("url") or "").lower()
    if re.search(r"(?:^|/)(?:nfl[-_/]?news[-_/]?round[-_]?up|news[-_/]?round[-_]?up)(?:/|$)", url):
        return {"content_type": "news-round-up", "confidence": 1.0, "reasoning": "URL matches roundup pattern"}

    title = _strip_html_and_ws(content.get("title", ""), 200)
    main_content = _strip_html_and_ws(content.get("main_content", ""), 1000)
    if not (title or main_content):
        return {"content_type": "empty_content", "confidence": 1.0, "reasoning": "No title or content"}

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

    if classify_client is None:
        return {"content_type": "empty_content", "confidence": 0.2, "reasoning": "LLM unavailable in CI"}

    try:
        result = _run_classification(classify_client, classify_model, prompt)
    except Exception as e:
        print(f"Error analyzing content type (mini): {e}")
        try:
            print("⚠️ Escalating classification to gpt-5 due to error...")
            gpt5_client, gpt5_model = initialize_llm_client("gpt-5")
            return _run_classification(gpt5_client, gpt5_model, prompt)
        except Exception as e2:
            print(f"Escalation to gpt-5 failed: {e2}")
            return {"content_type": "empty_content", "confidence": 0.2, "reasoning": f"Error: {e}; escalation failed: {e2}"}

    conf = result["confidence"]
    ctype = result["content_type"]
    escalate = (conf < 0.65) or (ctype in {"empty_content", "wrong_content"} and conf < 0.6)
    if escalate:
        print("⚠️ Escalating classification to gpt-5 (low confidence/uncertain)...")
        try:
            gpt5_client, gpt5_model = initialize_llm_client("gpt-5")
            return _run_classification(gpt5_client, gpt5_model, prompt)
        except Exception as e:
            print(f"Escalation to gpt-5 failed: {e}")
            return result

    return result

# ---------------------------
# I/O + processing pipeline
# ---------------------------
def _join_sections(content_data: Any) -> Tuple[str, str]:
    """
    Normalize structures to (text, url). We store our own Crawl results as strings,
    so this mostly returns (string, url) with empty url unless included.
    """
    url = ""
    if isinstance(content_data, str):
        return content_data, url
    if isinstance(content_data, dict):
        url = content_data.get("url", "") or content_data.get("source_url", "")
        blocks = content_data.get("blocks")
        if isinstance(blocks, list):
            text = "\n\n".join("\n".join(section.get("content", [])) for section in blocks if isinstance(section, dict))
            if text:
                return text, url
        if "Content" in content_data and isinstance(content_data["Content"], str):
            return content_data["Content"], url
        return "", url
    if isinstance(content_data, list):
        text = "\n\n".join("\n".join(section.get("content", [])) for section in content_data if isinstance(section, dict))
        return text, url
    return "", url

def save_json(obj: Any, path: str) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
        print(f"Saved: {path}")
    except Exception as e:
        print(f"Error saving {path}: {e}")

def save_cleaned_content(cleaned_data: Dict[str, Dict[str, str]], output_file: str) -> None:
    save_json(cleaned_data, output_file)

def load_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return {}


# -----------------
# Phase 1: Crawl4AI
# -----------------
async def crawl_phase_write_extracted_json(output_path: str) -> Dict[str, str]:
    """
    1) Fetch unprocessed articles from DB
    2) Run Crawl4AI extract_main_content for each
    3) Write extracted_contents.json
    Returns the in-memory dict as well.
    """
    unprocessed_articles = get_unprocessed_articles()
    extracted_contents: Dict[str, str] = {}

    for article in unprocessed_articles:
        article_id = article["id"]
        url = unquote(article["url"])
        article_url = url if url.startswith("http") else "https://www." + url
        print(f"Extracting content from {article_url}")
        try:
            extracted = await extract_main_content(article_url)
            if not extracted or extracted.startswith("Failed to extract"):
                print(f"Warning: Extraction issue for {article_url}")
            else:
                print(f"Successfully extracted {len(extracted)} characters from {article_url}")
            extracted_contents[article_id] = extracted
        except Exception as e:
            print(f"[ERROR] Failed to extract content from {article_url}: {e}")
            extracted_contents[article_id] = f"Extraction error: {str(e)}"

    save_json(extracted_contents, output_path)
    print("Content extraction complete.")
    return extracted_contents

# ---------------------------
# Phase 2: Post-processing
# ---------------------------
def process_all_articles(extracted_data: Dict[str, Any], url_lookup: Dict[str, str]) -> Dict[str, Dict[str, str]]:
    """
    Process all articles using OpenAI LLMs + enrichment.
    url_lookup: mapping of article_id -> url (so we can enrich/classify with URL).
    """
    processed: Dict[str, Dict[str, str]] = {}
    for article_id, content_data in extracted_data.items():
        try:
            raw_content, _ = _join_sections(content_data)
            url_for_enrichment = url_lookup.get(str(article_id)) or url_lookup.get(article_id) or ""

            # If Crawl4AI gave tiny text, try to enrich using the URL (doesn't alter Crawl4AI)
            if len(raw_content) < 800 and url_for_enrichment:
                raw_content = enrich_content_from_url_if_needed(raw_content, url_for_enrichment)

            # Extract structured fields (nano → mini)
            article = extract_content_with_llm(raw_content)

            # Normalize date
            article["cleaned_date_timestamptz"] = clean_publication_date(article.get("publication_date", "")) if article.get("publication_date") else None

            # Classify (mini → gpt-5)
            classified = analyze_content_type({**article, "url": url_for_enrichment})
            article["content_type"] = classified["content_type"]
            article["type_confidence"] = classified["confidence"]
            article["type_reasoning"] = classified["reasoning"]

            processed[article_id] = article

            # Debug summary
            title_print = article["title"]
            print(f"Processed article {article_id}:")
            print(f"  Title: {title_print[:70]}..." if len(title_print) > 70 else f"  Title: {title_print}")
            print(f"  Date: {article['publication_date']}")
            if article["cleaned_date_timestamptz"]:
                print(f"  Cleaned Date: {article['cleaned_date_timestamptz']}")
            print(f"  Author: {article['author']}")
            print(f"  Content length: {len(article['main_content'])} chars")
            print(f"  Content type: {article['content_type']} (confidence: {article['type_confidence']:.2f})\n")

        except Exception as e:
            print(f"Error processing article {article_id}: {e}")
    return processed

# -----
# Main
# -----
def main():
    base_dir = os.path.dirname(__file__)
    extracted_path = os.path.join(base_dir, "extracted_contents.json")
    cleaned_path = os.path.join(base_dir, "cleaned_contents.json")

    # Phase 1: Crawl4AI (write extracted_contents.json)
    # Also build a URL lookup so post-processing can enrich/classify
    # If your get_unprocessed_articles() returns URLs, we capture them here.
    # We run the crawl and collect extracted texts.
    loop = asyncio.get_event_loop()
    extracted = loop.run_until_complete(crawl_phase_write_extracted_json(extracted_path))

    # Build a {id: url} lookup (so classification/enrichment can use it)
    url_lookup: Dict[str, str] = {}
    try:
        for a in get_unprocessed_articles():
            url_lookup[str(a["id"])] = unquote(a["url"]) if a.get("url") else ""
    except Exception:
        pass  # non-fatal; enrichment just won’t have URLs

    # Phase 2: Post-processing
    cleaned_articles = process_all_articles(extracted, url_lookup)

    # Save cleaned content
    save_cleaned_content(cleaned_articles, cleaned_path)

    # Summary
    print(f"Processed {len(cleaned_articles)} articles.")
    empty_titles = sum(1 for a in cleaned_articles.values() if not a["title"])
    empty_dates = sum(1 for a in cleaned_articles.values() if not a["publication_date"])
    empty_content = sum(1 for a in cleaned_articles.values() if not a["main_content"])
    print(f"Articles with empty titles: {empty_titles}")
    print(f"Articles with empty dates: {empty_dates}")
    print(f"Articles with empty content: {empty_content}")

if __name__ == "__main__":
    # Allow a one-off mode later if you want, e.g., --process-existing
    main()
