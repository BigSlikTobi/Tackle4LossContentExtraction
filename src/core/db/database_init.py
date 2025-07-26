"""
Centralized Supabase client management for the application.
This module provides a singleton Supabase client that can be shared across all modules.
"""
from supabase import create_client, Client
import os
import sys
import logging
from dotenv import load_dotenv
from typing import Optional

logger = logging.getLogger(__name__)

class SupabaseConnection:
    _instance: Optional['SupabaseConnection'] = None
    _client: Optional[Client] = None
    
    def __new__(cls) -> 'SupabaseConnection':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Initialize the Supabase client with proper error handling."""
        load_dotenv()
        
        SUPABASE_URL = os.getenv("SUPABASE_URL")
        SUPABASE_KEY = os.getenv("SUPABASE_KEY")
        IS_CI = os.getenv("CI") == 'true' or os.getenv("GITHUB_ACTIONS") == 'true'
        
        if SUPABASE_URL and SUPABASE_KEY and not IS_CI:
            try:
                self._client = create_client(SUPABASE_URL, SUPABASE_KEY)
                logger.info("Supabase client initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Supabase client: {e}")
                self._client = None
        elif IS_CI and SUPABASE_URL and SUPABASE_KEY and not SUPABASE_KEY.startswith('test-'):
            try:
                self._client = create_client(SUPABASE_URL, SUPABASE_KEY)
                logger.info("Supabase client initialized in CI environment")
            except Exception as e:
                logger.warning(f"Failed to initialize Supabase client in CI: {e}")
                self._client = None
        elif not IS_CI and (not SUPABASE_URL or not SUPABASE_KEY):
            logger.error("SUPABASE_URL and/or SUPABASE_KEY environment variables are not set.")
            if not IS_CI:
                sys.exit(1)
        else:
            logger.warning("Supabase credentials not available or in CI mode. Running without database access.")
    
    @property
    def client(self) -> Optional[Client]:
        """Get the Supabase client instance."""
        return self._client
    
    def is_connected(self) -> bool:
        """Check if the client is properly initialized."""
        return self._client is not None

# Convenience function to get the client
def get_supabase_client() -> Optional[Client]:
    """Get the shared Supabase client instance."""
    return SupabaseConnection().client