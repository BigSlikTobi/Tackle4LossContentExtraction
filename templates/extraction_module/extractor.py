"""
Example Content Extractor

This module provides content extraction functionality as a template example.

Template Usage:
1. Replace 'Example' with your module name throughout this file
2. Implement the actual extraction logic in the extract() method
3. Update get_supported_domains() with your target domains
4. Customize metadata extraction and text cleaning as needed
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import logging
from urllib.parse import urlparse

try:
    from .config import ExampleConfig
except ImportError:
    from config import ExampleConfig


logger = logging.getLogger(__name__)


class BaseExtractor(ABC):
    """Base class for all content extractors."""
    
    @abstractmethod
    def extract(self, url: str) -> Dict[str, Any]:
        """Extract content from the given URL."""
        pass
    
    @abstractmethod
    def validate_url(self, url: str) -> bool:
        """Validate if the URL can be processed by this extractor."""
        pass
    
    @abstractmethod
    def get_supported_domains(self) -> List[str]:
        """Return list of supported domains."""
        pass


class ExampleExtractor(BaseExtractor):
    """
    Example content extractor template.
    
    This extractor serves as a template for creating new extractors.
    Replace 'Example' with your actual extractor name and implement
    the extraction logic for your specific use case.
    
    Template Usage:
    1. Rename this class to match your target (e.g., ESPNExtractor)
    2. Update get_supported_domains() with your target domains
    3. Implement actual extraction logic in extract()
    4. Customize _extract_metadata() for your needs
    """
    
    def __init__(self, config: Optional[ExampleConfig] = None):
        """
        Initialize the extractor.
        
        Args:
            config: Configuration object for the extractor
        """
        self.config = config or ExampleConfig()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def extract(self, url: str) -> Dict[str, Any]:
        """
        Extract content from the given URL.
        
        Args:
            url: URL to extract content from
            
        Returns:
            Dict containing extracted content with keys:
            - title: Article title
            - content: Main content text
            - author: Author information
            - publish_date: Publication date
            - metadata: Additional metadata
            
        Raises:
            ValueError: If URL is invalid or unsupported
            Exception: If extraction fails
        """
        if not self.validate_url(url):
            raise ValueError(f"Unsupported URL: {url}")
        
        try:
            self.logger.info(f"Starting extraction for URL: {url}")
            
            # TODO: Implement actual extraction logic
            # This is a template - replace with your implementation
            # 
            # Example implementation steps:
            # 1. Make HTTP request to URL
            # 2. Parse HTML with BeautifulSoup
            # 3. Extract title, content, author, date
            # 4. Clean and normalize text
            # 5. Extract metadata
            
            extracted_data = {
                'url': url,
                'title': '',
                'content': '',
                'author': '',
                'publish_date': None,
                'metadata': {}
            }
            
            self.logger.info(f"Successfully extracted content from: {url}")
            return extracted_data
            
        except Exception as e:
            self.logger.error(f"Failed to extract content from {url}: {str(e)}")
            raise
    
    def validate_url(self, url: str) -> bool:
        """
        Validate if the URL can be processed by this extractor.
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is supported, False otherwise
        """
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            
            # Remove www. prefix for comparison
            if domain.startswith('www.'):
                domain = domain[4:]
            
            return domain in self.get_supported_domains()
            
        except Exception as e:
            self.logger.warning(f"Failed to validate URL {url}: {str(e)}")
            return False
    
    def get_supported_domains(self) -> List[str]:
        """
        Return list of supported domains.
        
        Returns:
            List of domain names this extractor supports
            
        Template Note:
            Replace these example domains with your actual target domains
        """
        # TODO: Replace with actual supported domains
        return [
            'example.com',
            'sample.org'
        ]
    
    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize extracted text.
        
        Args:
            text: Raw text to clean
            
        Returns:
            Cleaned and normalized text
        """
        if not text:
            return ''
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # TODO: Add more cleaning logic as needed
        # - Remove unwanted characters
        # - Fix encoding issues
        # - Normalize quotes, etc.
        
        return text.strip()
    
    def _extract_metadata(self, soup) -> Dict[str, Any]:
        """
        Extract metadata from the page.
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            Dictionary containing metadata
            
        Template Note:
            Implement metadata extraction based on your target site's structure
        """
        metadata = {}
        
        # TODO: Implement metadata extraction
        # Example implementations:
        # - Open Graph tags: soup.find('meta', property='og:title')
        # - Twitter Card tags: soup.find('meta', attrs={'name': 'twitter:title'})
        # - Schema.org markup: soup.find('script', type='application/ld+json')
        # - Standard meta tags: soup.find('meta', attrs={'name': 'description'})
        
        return metadata
