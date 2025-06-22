"""
Test suite for the Example Content Extractor template.

This file serves as a template for testing extractor modules.
Copy and modify this when creating new extractors.
"""

import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add the project root to sys.path for imports
sys.path.insert(0, os.path.abspath('../../../'))

from templates.extraction_module.extractor import ExampleExtractor, BaseExtractor
from templates.extraction_module.config import ExampleConfig


class TestExampleConfig:
    """Test the Example configuration class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ExampleConfig()
        
        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.extract_images is True
        assert config.extract_links is True
        assert config.extract_metadata is True
    
    def test_config_validation(self):
        """Test configuration validation."""
        config = ExampleConfig()
        
        # Valid configuration should pass
        assert config.validate() is True
        
        # Invalid configurations should raise ValueError
        config.timeout = -1
        with pytest.raises(ValueError, match="Timeout must be positive"):
            config.validate()
        
        config.timeout = 30
        config.max_retries = -1
        with pytest.raises(ValueError, match="Max retries cannot be negative"):
            config.validate()
    
    def test_get_headers(self):
        """Test HTTP headers generation."""
        config = ExampleConfig()
        headers = config.get_headers()
        
        assert 'User-Agent' in headers
        assert 'Accept' in headers
        assert 'Connection' in headers
        assert headers['User-Agent'] == config.user_agent
    
    def test_config_presets(self):
        """Test configuration presets."""
        from templates.extraction_module.config import FAST_CONFIG, COMPREHENSIVE_CONFIG
        
        # Fast config should have shorter timeout and fewer features
        assert FAST_CONFIG.timeout == 10
        assert FAST_CONFIG.max_retries == 1
        assert FAST_CONFIG.extract_images is False
        
        # Comprehensive config should have longer timeout and all features
        assert COMPREHENSIVE_CONFIG.timeout == 60
        assert COMPREHENSIVE_CONFIG.max_retries == 5
        assert COMPREHENSIVE_CONFIG.extract_images is True


class TestBaseExtractor:
    """Test the abstract BaseExtractor class."""
    
    def test_base_extractor_is_abstract(self):
        """Test that BaseExtractor cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseExtractor()


class TestExampleExtractor:
    """Test the Example extractor implementation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = ExampleConfig()
        self.extractor = ExampleExtractor(self.config)
    
    def test_extractor_initialization(self):
        """Test extractor initialization."""
        # Test with custom config
        extractor = ExampleExtractor(self.config)
        assert extractor.config == self.config
        
        # Test with default config
        extractor = ExampleExtractor()
        assert isinstance(extractor.config, ExampleConfig)
    
    def test_get_supported_domains(self):
        """Test supported domains list."""
        domains = self.extractor.get_supported_domains()
        
        assert isinstance(domains, list)
        assert len(domains) > 0
        assert 'example.com' in domains
        assert 'sample.org' in domains
    
    def test_validate_url(self):
        """Test URL validation."""
        # Valid URLs for supported domains
        assert self.extractor.validate_url('https://example.com/article') is True
        assert self.extractor.validate_url('http://www.example.com/news') is True
        assert self.extractor.validate_url('https://sample.org/story') is True
        
        # Invalid URLs
        assert self.extractor.validate_url('https://unsupported.com/article') is False
        assert self.extractor.validate_url('invalid-url') is False
        assert self.extractor.validate_url('') is False
    
    def test_extract_unsupported_url(self):
        """Test extraction with unsupported URL."""
        with pytest.raises(ValueError, match="Unsupported URL"):
            self.extractor.extract('https://unsupported.com/article')
    
    def test_extract_supported_url(self):
        """Test extraction with supported URL."""
        url = 'https://example.com/article'
        result = self.extractor.extract(url)
        
        # Check return structure
        assert isinstance(result, dict)
        assert 'url' in result
        assert 'title' in result
        assert 'content' in result
        assert 'author' in result
        assert 'publish_date' in result
        assert 'metadata' in result
        
        # Check URL is preserved
        assert result['url'] == url
    
    def test_clean_text(self):
        """Test text cleaning functionality."""
        # Test normal text cleaning
        dirty_text = "  Multiple   spaces   and\n\nline\nbreaks  "
        clean_text = self.extractor._clean_text(dirty_text)
        assert clean_text == "Multiple spaces and line breaks"
        
        # Test empty text
        assert self.extractor._clean_text("") == ""
        assert self.extractor._clean_text(None) == ""
    
    def test_extract_metadata(self):
        """Test metadata extraction."""
        # Mock BeautifulSoup object
        mock_soup = Mock()
        metadata = self.extractor._extract_metadata(mock_soup)
        
        # Should return a dictionary (even if empty in template)
        assert isinstance(metadata, dict)


class TestTemplateUsage:
    """Test template usage and customization scenarios."""
    
    def test_template_customization_example(self):
        """Example of how to customize the template."""
        
        class CustomExtractor(ExampleExtractor):
            """Example of customizing the template for a specific site."""
            
            def get_supported_domains(self) -> list:
                return ['custom-site.com', 'another-site.org']
            
            def extract(self, url: str) -> dict:
                # Custom extraction logic would go here
                if not self.validate_url(url):
                    raise ValueError(f"Unsupported URL: {url}")
                
                return {
                    'url': url,
                    'title': 'Custom Title',
                    'content': 'Custom Content',
                    'author': 'Custom Author',
                    'publish_date': '2025-06-22',
                    'metadata': {'custom': 'data'}
                }
        
        # Test the custom extractor
        custom_config = ExampleConfig()
        extractor = CustomExtractor(custom_config)
        
        # Test custom domains
        assert 'custom-site.com' in extractor.get_supported_domains()
        assert extractor.validate_url('https://custom-site.com/article') is True
        assert extractor.validate_url('https://example.com/article') is False
        
        # Test custom extraction
        result = extractor.extract('https://custom-site.com/article')
        assert result['title'] == 'Custom Title'
        assert result['metadata']['custom'] == 'data'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
