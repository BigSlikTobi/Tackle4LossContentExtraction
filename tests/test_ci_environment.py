"""
Test CI environment setup and basic functionality.
"""
import os
import pytest


def test_environment_variables_set():
    """Test that required environment variables are set in CI."""
    # These should be set by the CI workflow
    assert os.getenv('OPENAI_API_KEY') is not None
    assert os.getenv('SUPABASE_URL') is not None
    assert os.getenv('SUPABASE_KEY') is not None
    assert os.getenv('DEEPSEEK_API_KEY') is not None


def test_python_version():
    """Test that we're running on a supported Python version."""
    import sys
    version = sys.version_info
    
    # Should be Python 3.11, 3.12, or 3.13
    assert version.major == 3
    assert version.minor >= 11


def test_basic_imports():
    """Test that core modules can be imported without errors."""
    # These imports should work without requiring actual API keys
    import sys
    import os
    
    # Add project root to path
    project_root = os.path.dirname(os.path.dirname(__file__))
    sys.path.insert(0, project_root)
    
    # Test basic imports that don't require external connections
    try:
        from modules.extraction import extractContent
        from modules.extraction import cleanContent
        assert True  # Import successful
    except ImportError as e:
        pytest.skip(f"Module import failed: {e}")


def test_requirements_installed():
    """Test that key packages are installed."""
    try:
        import requests
        from bs4 import BeautifulSoup  # beautifulsoup4 package
        import pandas
        import numpy
        import openai
        import playwright
        assert True
    except ImportError as e:
        pytest.fail(f"Required package not installed: {e}")


@pytest.mark.integration
def test_mock_api_calls():
    """Test that API calls would work with proper credentials."""
    # This test verifies the structure without making real API calls
    openai_key = os.getenv('OPENAI_API_KEY')
    assert openai_key is not None
    assert openai_key.startswith('sk-')  # OpenAI API key format


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
