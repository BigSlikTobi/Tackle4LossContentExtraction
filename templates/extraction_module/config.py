"""
Configuration for Example Content Extractor

Author: Tackle4Loss Development Team

This is a template configuration file. To customize:
1. Replace 'Example' with your module name
2. Adjust default values as needed
3. Add module-specific configuration options
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional


@dataclass
class ExampleConfig:
    """
    Configuration class for Example extractor.
    
    This class defines all configurable parameters for the content extraction
    process, including timeouts, retry logic, and extraction settings.
    
    Template Usage:
    - Replace 'Example' with your actual extractor name
    - Modify default values as needed for your use case
    - Add domain-specific configuration options
    """
    
    # Request settings
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # User agent for requests
    user_agent: str = "Mozilla/5.0 (compatible; Tackle4Loss Content Extractor)"
    
    # Content extraction settings
    min_content_length: int = 100
    max_content_length: int = 50000
    
    # Supported content types
    supported_content_types: Optional[List[str]] = None
    
    # Custom headers
    custom_headers: Optional[Dict[str, str]] = None
    
    # Extraction parameters
    extract_images: bool = True
    extract_links: bool = True
    extract_metadata: bool = True
    
    # Text processing
    clean_html: bool = True
    normalize_whitespace: bool = True
    remove_ads: bool = True
    
    # Error handling
    raise_on_error: bool = True
    log_level: str = "INFO"
    
    def __post_init__(self):
        """Initialize default values for mutable fields."""
        if self.supported_content_types is None:
            self.supported_content_types = [
                'text/html',
                'application/xhtml+xml'
            ]
        
        if self.custom_headers is None:
            self.custom_headers = {}
    
    def get_headers(self) -> Dict[str, str]:
        """
        Get complete headers for HTTP requests.
        
        Returns:
            Dictionary of HTTP headers
        """
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Add custom headers
        headers.update(self.custom_headers)
        
        return headers
    
    def validate(self) -> bool:
        """
        Validate configuration parameters.
        
        Returns:
            True if configuration is valid
            
        Raises:
            ValueError: If configuration is invalid
        """
        if self.timeout <= 0:
            raise ValueError("Timeout must be positive")
        
        if self.max_retries < 0:
            raise ValueError("Max retries cannot be negative")
        
        if self.retry_delay < 0:
            raise ValueError("Retry delay cannot be negative")
        
        if self.min_content_length < 0:
            raise ValueError("Min content length cannot be negative")
        
        if self.max_content_length <= self.min_content_length:
            raise ValueError("Max content length must be greater than min content length")
        
        return True


# Default configuration instance
DEFAULT_CONFIG = ExampleConfig()


# Configuration presets for different use cases
FAST_CONFIG = ExampleConfig(
    timeout=10,
    max_retries=1,
    extract_images=False,
    extract_links=False,
    extract_metadata=False
)

COMPREHENSIVE_CONFIG = ExampleConfig(
    timeout=60,
    max_retries=5,
    retry_delay=2.0,
    extract_images=True,
    extract_links=True,
    extract_metadata=True,
    min_content_length=50,
    max_content_length=100000
)
