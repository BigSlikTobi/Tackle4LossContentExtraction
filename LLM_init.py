#!/usr/bin/env python3
"""
This module initializes the LLM client for use across different modules.
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def initialize_llm_client():
    """
    Initialize the OpenAI client with Deepseek configuration.
    
    Returns:
        OpenAI client instance configured for Deepseek API
    """
    # Check for API key
    if not os.getenv("DEEPSEEK_API_KEY"):
        raise ValueError("Error: DEEPSEEK_API_KEY environment variable not set")
    
    # Initialize OpenAI client with Deepseek configuration
    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com"
    )
    
    return client