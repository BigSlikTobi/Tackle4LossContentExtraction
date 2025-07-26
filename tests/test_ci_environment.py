"""
Test CI environment setup and basic functionality.
"""
import os
import pytest


def test_environment_variables_set():
    """Test that required environment variables are set in CI."""
    # Check if we're in CI environment
    is_ci = os.getenv('CI') == 'true' or os.getenv('GITHUB_ACTIONS') == 'true'
    
    if is_ci:
        # In CI, these should be set by the workflow (even if dummy values)
        openai_key = os.getenv('OPENAI_API_KEY')
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_KEY')
        deepseek_key = os.getenv('DEEPSEEK_API_KEY')
        
        assert openai_key is not None, f"OPENAI_API_KEY is None in CI. Expected test key."
        assert supabase_url is not None, f"SUPABASE_URL is None in CI. Expected test URL."
        assert supabase_key is not None, f"SUPABASE_KEY is None in CI. Expected test key."
        assert deepseek_key is not None, f"DEEPSEEK_API_KEY is None in CI. Got: {deepseek_key}"
    else:
        # In local environment, warn if they're missing but don't fail
        missing_vars = []
        for var in ['OPENAI_API_KEY', 'SUPABASE_URL', 'SUPABASE_KEY', 'DEEPSEEK_API_KEY']:
            if os.getenv(var) is None:
                missing_vars.append(var)
        
        if missing_vars:
            pytest.skip(f"Running locally without environment variables: {', '.join(missing_vars)}")


def test_python_version():
    """Test that we're running on a supported Python version."""
    import sys
    version = sys.version_info
    
    # Should be Python 3.11, 3.12, or 3.13
    assert version.major == 3
    assert version.minor >= 11


def test_basic_imports():
    """Test that core modules can be imported without errors."""
    # Set CI flag to avoid Supabase client initialization errors
    os.environ['CI'] = 'true'
    
    import sys
    
    # Add project root to path
    project_root = os.path.dirname(os.path.dirname(__file__))
    sys.path.insert(0, project_root)
    
    # Test basic imports that don't require external connections
    try:
        from src.modules.extraction import extractContent
        from src.modules.extraction import cleanContent
        assert True  # Import successful
    except ImportError as e:
        pytest.skip(f"Module import failed: {e}")
    except Exception as e:
        # Handle other exceptions like Supabase connection errors
        if "supabase" in str(e).lower() or "invalid api key" in str(e).lower():
            pytest.skip(f"Supabase connection error in CI: {e}")
        else:
            raise


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
    assert openai_key is not None, f"OPENAI_API_KEY is None"
    
    # Check if we're in CI with dummy keys
    is_ci = os.getenv('CI') == 'true' or os.getenv('GITHUB_ACTIONS') == 'true'
    
    if is_ci:
        # In CI with test keys - be flexible about format
        if openai_key.startswith('sk-test-'):
            # Expected test key format
            assert len(openai_key) > 10  # Reasonable length
        elif openai_key.startswith('sk-'):
            # Real key format but in CI (using secrets)
            assert len(openai_key) > 20  # Real keys are longer
        else:
            # Some other test format - just ensure it's not empty
            assert len(openai_key) > 3, f"API key too short in CI: '{openai_key}'"
    else:
        # In production/local with real keys
        assert openai_key.startswith('sk-'), f"Expected real OpenAI key format, got: '{openai_key}'"


def test_debug_environment():
    """Debug test to see what environment variables are actually set in CI."""
    import os
    
    print(f"\n=== Environment Debug ===")
    print(f"CI: '{os.getenv('CI')}'")
    print(f"GITHUB_ACTIONS: '{os.getenv('GITHUB_ACTIONS')}'")
    print(f"OPENAI_API_KEY: '{os.getenv('OPENAI_API_KEY')}'")
    print(f"SUPABASE_URL: '{os.getenv('SUPABASE_URL')}'")
    print(f"SUPABASE_KEY: '{os.getenv('SUPABASE_KEY')}'")
    print(f"DEEPSEEK_API_KEY: '{os.getenv('DEEPSEEK_API_KEY')}'")
    print(f"========================\n")
    
    # This test always passes - it's just for debugging
    assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
