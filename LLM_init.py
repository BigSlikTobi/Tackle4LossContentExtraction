#!/usr/bin/env python3
"""
This module initializes the LLM client for use across different modules.
"""

import os
from openai import OpenAI
from dotenv import load_dotenv
from typing import Literal

# Load environment variables from .env file
load_dotenv()

# Available models configuration
ModelType = Literal["deepseek", "gpt-4.1-nano-2025-04-14"]
MODEL_CONFIGS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "api_key_env": "DEEPSEEK_API_KEY",
        "model": "deepseek-chat"  # Add the specific model name if needed
    },
    "gpt-4.1-nano-2025-04-14": {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "model": "gpt-4.1-nano-2025-04-14"
    }
}

def initialize_llm_client(model_type: ModelType = "deepseek"):
    """
    Initialize the OpenAI client with specified model configuration.
    
    Args:
        model_type: The type of model to use ('deepseek' or 'gpt-4.1-nano-2025-04-14')
    
    Returns:
        tuple: (OpenAI client instance, model name)
    
    Raises:
        ValueError: If the required API key is not set
    """
    # Handle the case where model_type is still "gpt-4o-mini" from environment variable
    if model_type == "gpt-4o-mini":
        print("Warning: 'gpt-4o-mini' model type is deprecated, using 'gpt-4.1-nano-2025-04-14' instead.")
        model_type = "gpt-4.1-nano-2025-04-14"
    
    try:
        config = MODEL_CONFIGS[model_type]
    except KeyError:
        print(f"Warning: Unknown model type '{model_type}', falling back to 'gpt-4.1-nano-2025-04-14'.")
        model_type = "gpt-4.1-nano-2025-04-14"
        config = MODEL_CONFIGS[model_type]
    
    api_key = os.getenv(config["api_key_env"])
    
    if not api_key:
        raise ValueError(f"Error: {config['api_key_env']} environment variable not set")
    
    client = OpenAI(
        api_key=api_key,
        base_url=config["base_url"]
    )
    
    print(f"DEBUG: Using model: {config['model']}")
    
    return client, config["model"]