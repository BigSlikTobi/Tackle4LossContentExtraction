# {MODULE_NAME} Content Extractor

Author: {AUTHOR}  
Version: 1.0.0

## Overview

This module provides content extraction functionality for {DESCRIPTION}. It implements the standard Tackle4Loss extractor interface and provides robust content extraction with configurable settings.

## Features

- **URL Validation**: Validates URLs before processing
- **Content Extraction**: Extracts title, content, author, and publication date
- **Metadata Extraction**: Extracts Open Graph, Twitter Card, and Schema.org metadata
- **Image Extraction**: Optionally extracts images from content
- **Link Extraction**: Optionally extracts links from content
- **Text Cleaning**: Removes unwanted elements and normalizes text
- **Error Handling**: Comprehensive error handling and logging
- **Configurable**: Highly configurable extraction parameters

## Usage

### Basic Usage

```python
from modules.extraction.{module_name} import {MODULE_NAME}Extractor

# Create extractor instance
extractor = {MODULE_NAME}Extractor()

# Extract content
result = extractor.extract('https://example.com/article')

print(result['title'])
print(result['content'])
```

### With Custom Configuration

```python
from modules.extraction.{module_name} import {MODULE_NAME}Extractor, {MODULE_NAME}Config

# Create custom configuration
config = {MODULE_NAME}Config(
    timeout=60,
    max_retries=5,
    extract_images=True,
    extract_metadata=True
)

# Create extractor with custom config
extractor = {MODULE_NAME}Extractor(config=config)

# Extract content
result = extractor.extract('https://example.com/article')
```

### Using Configuration Presets

```python
from modules.extraction.{module_name} import {MODULE_NAME}Extractor
from modules.extraction.{module_name}.config import FAST_CONFIG, COMPREHENSIVE_CONFIG

# Use fast configuration (minimal extraction)
fast_extractor = {MODULE_NAME}Extractor(config=FAST_CONFIG)

# Use comprehensive configuration (full extraction)
comprehensive_extractor = {MODULE_NAME}Extractor(config=COMPREHENSIVE_CONFIG)
```

## Supported Domains

This extractor supports the following domains:

- example.com
- sample.org

*Note: Update the `get_supported_domains()` method to reflect actual supported domains.*

## Configuration Options

### Request Settings
- `timeout`: Request timeout in seconds (default: 30)
- `max_retries`: Maximum number of retry attempts (default: 3)
- `retry_delay`: Delay between retries in seconds (default: 1.0)
- `user_agent`: User agent string for requests

### Content Extraction
- `min_content_length`: Minimum content length to consider valid (default: 100)
- `max_content_length`: Maximum content length to extract (default: 50000)
- `extract_images`: Whether to extract images (default: True)
- `extract_links`: Whether to extract links (default: True)
- `extract_metadata`: Whether to extract metadata (default: True)

### Text Processing
- `clean_html`: Whether to clean HTML content (default: True)
- `normalize_whitespace`: Whether to normalize whitespace (default: True)
- `remove_ads`: Whether to remove advertisement elements (default: True)

## Output Format

The extractor returns a dictionary with the following structure:

```python
{
    'url': 'https://example.com/article',
    'title': 'Article Title',
    'content': 'Main article content...',
    'author': 'Author Name',
    'publish_date': '2024-01-01T12:00:00Z',  # ISO format or None
    'metadata': {
        'description': 'Article description',
        'keywords': ['keyword1', 'keyword2'],
        'images': [
            {
                'url': 'https://example.com/image.jpg',
                'alt': 'Image description',
                'title': 'Image title'
            }
        ],
        'links': [
            {
                'url': 'https://example.com/link',
                'text': 'Link text',
                'title': 'Link title'
            }
        ]
    }
}
```

## Error Handling

The extractor handles various error conditions:

- **Invalid URLs**: Raises `ValueError` for unsupported or malformed URLs
- **Network Errors**: Retries with exponential backoff
- **Parsing Errors**: Logs errors and returns partial data when possible
- **Content Too Short/Long**: Validates content length

## Logging

The extractor uses Python's logging module. Configure logging level in your application:

```python
import logging
logging.getLogger('modules.extraction.{module_name}').setLevel(logging.DEBUG)
```

## Testing

Run the module tests:

```bash
python -m pytest tests/test_{module_name}/ -v
```

## Implementation Notes

### TODO Items

The following items need to be implemented:

1. **Domain Support**: Update `get_supported_domains()` with actual domains
2. **Extraction Logic**: Implement the core extraction algorithm in `extract()`
3. **Author Extraction**: Add logic to extract author information
4. **Date Extraction**: Add logic to extract publication dates
5. **Content Selectors**: Update content selectors for target websites
6. **Metadata Extraction**: Implement comprehensive metadata extraction

### Customization

To customize this extractor for specific websites:

1. Update the supported domains list
2. Modify content selectors in the extraction logic
3. Add site-specific parsing rules
4. Update metadata extraction for site-specific schemas
5. Adjust text cleaning rules as needed

## Dependencies

This module requires:

- beautifulsoup4: HTML parsing
- requests: HTTP requests
- lxml: Fast XML/HTML parsing (optional but recommended)

Install dependencies:

```bash
pip install beautifulsoup4 requests lxml
```
