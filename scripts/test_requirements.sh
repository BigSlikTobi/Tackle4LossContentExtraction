#!/bin/bash

# Test script to verify requirements.txt compatibility
# This script creates a temporary virtual environment and tests the requirements

set -e

echo "=== Testing requirements.txt compatibility ==="

# Create temporary directory for testing
TEST_DIR=$(mktemp -d)
echo "Using temporary directory: $TEST_DIR"

cd "$TEST_DIR"

# Create virtual environment
echo "Creating test virtual environment..."
python3 -m venv test_env
source test_env/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "Installing requirements from requirements.txt..."
pip install -r "$(dirname "$0")/../requirements.txt"

# Test imports of key packages
echo "Testing key package imports..."
python -c "
import crawl4ai
import litellm
import nest_asyncio
import requests
import supabase
import playwright
import openai
import yaml
import httpx
import numpy
import sklearn
import pandas
import beautifulsoup4
import lxml
import nfl_data_py
print('✅ All key packages imported successfully!')
"

# Test Playwright browser installation
echo "Testing Playwright browser installation..."
python -m playwright install chromium --with-deps

# Test basic Playwright functionality
echo "Testing basic Playwright functionality..."
python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto('https://httpbin.org/status/200')
    assert page.title()
    browser.close()
print('✅ Playwright functionality test passed!')
"

echo "✅ All tests passed! Requirements.txt is compatible."

# Cleanup
cd /
rm -rf "$TEST_DIR"
echo "Cleanup completed."
