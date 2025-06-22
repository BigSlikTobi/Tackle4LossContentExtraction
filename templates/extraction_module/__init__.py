"""
Example Content Extractor Module Template

Author: Tackle4Loss Development Team
Description: Template module for creating content extractors

This is a template for creating new content extractor modules.
To use this template:
1. Copy this directory to your desired location
2. Replace 'Example' with your module name
3. Replace placeholder text with your implementation
4. Update the extractor logic in extractor.py
"""

try:
    from .extractor import ExampleExtractor
    from .config import ExampleConfig
except ImportError:
    from extractor import ExampleExtractor
    from config import ExampleConfig

__all__ = ['ExampleExtractor', 'ExampleConfig']
__version__ = '1.0.0'

# Template usage instructions:
# 1. Replace 'Example' with your actual module name (e.g., 'ESPN', 'Reuters')
# 2. Update the class names in extractor.py and config.py accordingly
# 3. Implement your specific extraction logic
