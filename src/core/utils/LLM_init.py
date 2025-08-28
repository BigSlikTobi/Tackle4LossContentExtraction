#!/usr/bin/env python3
"""
This module initializes the LLM client for use across different modules.
It supports OpenAI GPT-5 family (gpt-5, gpt-5-mini, gpt-5-nano) and DeepSeek.
It preserves backward compatibility with 'gpt-4.1-nano-2025-04-14' by mapping it to 'gpt-5-nano'.
Designed for both local development and CI environments.
"""

import os
from typing import Literal, Tuple, Optional
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# CI flag
IS_CI = os.getenv("CI") == 'true' or os.getenv("GITHUB_ACTIONS") == 'true'

# -----------------------------
# Public model type annotation
# -----------------------------
ModelType = Literal[
    "deepseek",
    "gpt-5-nano",
    "gpt-5-mini",
    "gpt-5",
    # legacy alias kept for compatibility:
    "gpt-4.1-nano-2025-04-14",
]

# ----------------------------------
# Central model configuration table
# ----------------------------------
MODEL_CONFIGS = {
    # DeepSeek (optional)
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "api_key_env": "DEEPSEEK_API_KEY",
        "model": "deepseek-chat",
        "provider": "deepseek",
    },

    # GPT-5 family (OpenAI)
    "gpt-5-nano": {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "model": "gpt-5-nano",
        "provider": "openai",
    },
    "gpt-5-mini": {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "model": "gpt-5-mini",
        "provider": "openai",
    },
    "gpt-5": {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "model": "gpt-5",
        "provider": "openai",
    },

    # Legacy alias -> maps to gpt-5-nano
    "gpt-4.1-nano-2025-04-14": {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "model": "gpt-5-nano",
        "provider": "openai",
        "_alias_of": "gpt-5-nano",
    },
}

def _coerce_model_type(requested: str) -> str:
    """
    Map legacy names or unknown values to safe defaults.
    - Legacy 'gpt-4.1-nano-2025-04-14' -> 'gpt-5-nano'
    - Unknown -> 'gpt-5-nano' (prints warning)
    """
    if requested in MODEL_CONFIGS:
        # Print an alias notice if applicable
        alias_of = MODEL_CONFIGS[requested].get("_alias_of")
        if alias_of:
            print(f"INFO: Model '{requested}' is deprecated; using '{alias_of}'.")
            return alias_of
        return requested
    print(f"WARNING: Unknown model type '{requested}'. Falling back to 'gpt-5-nano'.")
    return "gpt-5-nano"

def initialize_llm_client(model_type: ModelType = "gpt-5-mini") -> Tuple[Optional[OpenAI], Optional[str]]:
    """
    Initialize and return an LLM client + model name for the requested type.
    Returns (client, model_name). In CI without API key, returns (None, None) and logs a warning.

    Typical usage in your pipeline:
      extract_client, extract_model   = initialize_llm_client("gpt-5-nano")  # fast extractor
      classify_client, classify_model = initialize_llm_client("gpt-5-mini")  # classifier
      # on-demand escalation:
      full_client, full_model         = initialize_llm_client("gpt-5")       # high-accuracy fallback
    """
    normalized_type = _coerce_model_type(model_type)
    config = MODEL_CONFIGS[normalized_type]

    api_key = os.getenv(config["api_key_env"])
    if not api_key:
        if IS_CI:
            print(f"WARNING: {config['api_key_env']} not set in CI. Returning (None, None).")
            return None, None
        raise ValueError(f"Error: {config['api_key_env']} environment variable not set")

    client = OpenAI(api_key=api_key, base_url=config["base_url"])
    print(f"DEBUG: Using provider='{config.get('provider')}', model='{config['model']}'")
    return client, config["model"]
