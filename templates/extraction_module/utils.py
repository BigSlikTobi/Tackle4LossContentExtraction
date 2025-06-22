"""
Utility functions for Example Content Extractor

Author: Tackle4Loss Development Team
"""

import re
import html
import logging
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, Tag


logger = logging.getLogger(__name__)


def clean_text(text: str) -> str:
    """
    Clean and normalize text content.
    
    Args:
        text: Raw text to clean
        
    Returns:
        Cleaned and normalized text
    """
    if not text:
        return ''
    
    # Decode HTML entities
    text = html.unescape(text)
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text


def extract_links(soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
    """
    Extract all links from the page.
    
    Args:
        soup: BeautifulSoup object
        base_url: Base URL for resolving relative links
        
    Returns:
        List of dictionaries containing link information
    """
    links = []
    
    for link in soup.find_all('a', href=True):
        href = link.get('href', '').strip()
        if not href:
            continue
        
        # Resolve relative URLs
        absolute_url = urljoin(base_url, href)
        
        # Get link text
        text = clean_text(link.get_text())
        
        # Get title attribute
        title = link.get('title', '').strip()
        
        links.append({
            'url': absolute_url,
            'text': text,
            'title': title
        })
    
    return links


def extract_images(soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
    """
    Extract all images from the page.
    
    Args:
        soup: BeautifulSoup object
        base_url: Base URL for resolving relative URLs
        
    Returns:
        List of dictionaries containing image information
    """
    images = []
    
    for img in soup.find_all('img', src=True):
        src = img.get('src', '').strip()
        if not src:
            continue
        
        # Resolve relative URLs
        absolute_url = urljoin(base_url, src)
        
        # Get alt text
        alt = img.get('alt', '').strip()
        
        # Get title attribute
        title = img.get('title', '').strip()
        
        # Get dimensions if available
        width = img.get('width')
        height = img.get('height')
        
        images.append({
            'url': absolute_url,
            'alt': alt,
            'title': title,
            'width': width,
            'height': height
        })
    
    return images


def extract_meta_tags(soup: BeautifulSoup) -> Dict[str, str]:
    """
    Extract meta tags from the page.
    
    Args:
        soup: BeautifulSoup object
        
    Returns:
        Dictionary of meta tag content
    """
    meta_data = {}
    
    # Standard meta tags
    for meta in soup.find_all('meta'):
        name = meta.get('name') or meta.get('property') or meta.get('http-equiv')
        content = meta.get('content')
        
        if name and content:
            meta_data[name.lower()] = content.strip()
    
    return meta_data


def find_main_content(soup: BeautifulSoup) -> Optional[Tag]:
    """
    Attempt to find the main content area of the page.
    
    Args:
        soup: BeautifulSoup object
        
    Returns:
        BeautifulSoup Tag containing main content, or None
    """
    # Try common content selectors
    content_selectors = [
        'main',
        'article',
        '[role="main"]',
        '.main-content',
        '.content',
        '.post-content',
        '.entry-content',
        '#content',
        '#main'
    ]
    
    for selector in content_selectors:
        content = soup.select_one(selector)
        if content:
            return content
    
    # Fallback: look for the largest text block
    text_blocks = soup.find_all(['div', 'section', 'article'])
    if text_blocks:
        # Sort by text length
        largest_block = max(text_blocks, key=lambda x: len(x.get_text()))
        return largest_block
    
    return None


def remove_unwanted_elements(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Remove unwanted elements from the soup.
    
    Args:
        soup: BeautifulSoup object to clean
        
    Returns:
        Cleaned BeautifulSoup object
    """
    # Elements to remove
    unwanted_selectors = [
        'script',
        'style',
        'nav',
        'header',
        'footer',
        'aside',
        '.advertisement',
        '.ads',
        '.sidebar',
        '.comments',
        '.social-share',
        '.related-posts'
    ]
    
    for selector in unwanted_selectors:
        for element in soup.select(selector):
            element.decompose()
    
    return soup


def validate_url(url: str) -> bool:
    """
    Validate if URL is properly formatted.
    
    Args:
        url: URL to validate
        
    Returns:
        True if URL is valid, False otherwise
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def get_domain(url: str) -> Optional[str]:
    """
    Extract domain from URL.
    
    Args:
        url: URL to extract domain from
        
    Returns:
        Domain name or None if invalid URL
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Remove www. prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        
        return domain
    except Exception:
        return None


def truncate_text(text: str, max_length: int = 1000, suffix: str = '...') -> str:
    """
    Truncate text to specified length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add when truncating
        
    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text
    
    # Try to break at word boundary
    truncated = text[:max_length - len(suffix)]
    last_space = truncated.rfind(' ')
    
    if last_space > max_length * 0.8:  # Don't truncate too much
        truncated = truncated[:last_space]
    
    return truncated + suffix
