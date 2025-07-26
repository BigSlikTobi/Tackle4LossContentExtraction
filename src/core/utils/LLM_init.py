#!/usr/bin/env python3
"""
This module initializes the LLM client for use across different modules.
It handles the configuration of the OpenAI client based on environment variables and model type.
It also provides a function to initialize the client with the specified model type.
It supports both DeepSeek and OpenAI models, allowing for flexible usage in different environments.
It is designed to be used in both local development and CI environments.
"""

import os
from openai import OpenAI
from dotenv import load_dotenv
from typing import Literal

# Load environment variables from .env file
load_dotenv()

# Check if running in CI environment and set a flag
IS_CI = os.getenv("CI") == 'true' or os.getenv("GITHUB_ACTIONS") == 'true'

# Available models configuration
ModelType = Literal["deepseek", "gpt-4.1-nano-2025-04-14"]
MODEL_CONFIGS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "api_key_env": "DEEPSEEK_API_KEY",
        "model": "deepseek-chat" 
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
    This function sets up the OpenAI client based on the provided model type.
    Args:
        model_type: The type of model to use  based on MODEL_CONFIGS.
        Defaults to "deepseek".
    Returns:
        tuple: (OpenAI client instance, model name)
    Raises:
        ValueError: If the required API key is not set in the environment variables.
        KeyError: If the model type is not recognized in MODEL_CONFIGS.
    """
    # Handle the case where model_type is still "gpt-4o-mini" from environment variable
    if model_type == "gpt-4o-mini":
        print("Using 'gpt-4.1-nano-2025-04-14' instead.")
        model_type = "gpt-4.1-nano-2025-04-14"
    
    try:
        config = MODEL_CONFIGS[model_type]
    except KeyError:
        print(f"Warning: Unknown model type '{model_type}', falling back to 'gpt-4.1-nano-2025-04-14'.")
        model_type = "gpt-4.1-nano-2025-04-14"
        config = MODEL_CONFIGS[model_type]
    
    api_key = os.getenv(config["api_key_env"])
    
    if not api_key:
        if IS_CI:
            print(f"WARNING: {config['api_key_env']} environment variable not set. LLM client will not be initialized.")
            return None, None
        raise ValueError(f"Error: {config['api_key_env']} environment variable not set")
    
    client = OpenAI(
        api_key=api_key,
        base_url=config["base_url"]
    )
    
    print(f"DEBUG: Using model: {config['model']}")
    
    return client, config["model"]