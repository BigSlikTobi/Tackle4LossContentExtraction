# Content Extraction Module Template

This template provides a standardized structure for creating new content extraction modules in the Tackle4Loss pipeline.

## Quick Start

1. Copy this template directory to create a new module:
   ```bash
   cp -r templates/extraction_module modules/extraction/my_new_extractor
   ```

2. Rename files and update placeholders:
   - Replace `{MODULE_NAME}` with your module name
   - Replace `{AUTHOR}` with your name
   - Replace `{DESCRIPTION}` with module description

3. Implement the required methods in your extractor class

4. Add tests in the tests directory

5. Update the main module's `__init__.py` to include your new extractor

## Template Structure

```
extraction_module/
├── __init__.py
├── extractor.py          # Main extractor class
├── config.py            # Configuration and constants
├── utils.py             # Helper functions
├── README.md            # Module documentation
└── tests/
    ├── __init__.py
    ├── test_extractor.py
    └── test_utils.py
```

## Implementation Guidelines

### Extractor Class Requirements

Your extractor must inherit from `BaseExtractor` and implement:

- `extract(url: str) -> Dict[str, Any]`: Main extraction method
- `validate_url(url: str) -> bool`: URL validation
- `get_supported_domains() -> List[str]`: Supported domains list

### Configuration

Use the `config.py` file to define:
- Module-specific settings
- Default parameters
- Domain patterns
- Error messages

### Testing

Ensure comprehensive test coverage:
- Happy path scenarios
- Error conditions
- Edge cases
- Performance benchmarks

### Documentation

Include detailed documentation:
- Module purpose and scope
- Usage examples
- API reference
- Configuration options
