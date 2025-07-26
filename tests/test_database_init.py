"""
Tests for the centralized Supabase client management module.
This module tests the SupabaseConnection singleton and related functionality.
"""
import unittest
from unittest.mock import patch, MagicMock, call
import os
import sys
import logging
from typing import Optional

# Import the module to be tested
from src.core.db.database_init import SupabaseConnection, get_supabase_client


class TestSupabaseConnection(unittest.TestCase):
    """Test cases for the SupabaseConnection singleton class."""

    def setUp(self):
        """Reset the singleton instance before each test."""
        # Clear the singleton instance to ensure clean state for each test
        SupabaseConnection._instance = None
        SupabaseConnection._client = None

    def tearDown(self):
        """Clean up after each test."""
        # Reset singleton state
        SupabaseConnection._instance = None
        SupabaseConnection._client = None

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.core.db.database_init.load_dotenv')
    @patch('src.core.db.database_init.create_client')
    def test_singleton_pattern(self, mock_create_client, mock_load_dotenv):
        """Test that SupabaseConnection follows singleton pattern."""
        # Arrange
        os.environ.update({
            'SUPABASE_URL': 'https://test.supabase.co',
            'SUPABASE_KEY': 'test_key'
        })
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Act
        instance1 = SupabaseConnection()
        instance2 = SupabaseConnection()

        # Assert
        self.assertIs(instance1, instance2)
        self.assertEqual(id(instance1), id(instance2))

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.core.db.database_init.load_dotenv')
    @patch('src.core.db.database_init.create_client')
    def test_successful_initialization_non_ci(self, mock_create_client, mock_load_dotenv):
        """Test successful client initialization in non-CI environment."""
        # Arrange
        os.environ.update({
            'SUPABASE_URL': 'https://test.supabase.co',
            'SUPABASE_KEY': 'test_key'
        })
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Act
        connection = SupabaseConnection()

        # Assert
        mock_load_dotenv.assert_called_once()
        mock_create_client.assert_called_once_with('https://test.supabase.co', 'test_key')
        self.assertEqual(connection.client, mock_client)
        self.assertTrue(connection.is_connected())

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.core.db.database_init.load_dotenv')
    @patch('src.core.db.database_init.create_client')
    def test_successful_initialization_ci_real_credentials(self, mock_create_client, mock_load_dotenv):
        """Test successful client initialization in CI with real credentials."""
        # Arrange
        os.environ.update({
            'CI': 'true',
            'SUPABASE_URL': 'https://real.supabase.co',
            'SUPABASE_KEY': 'real_key'
        })
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Act
        connection = SupabaseConnection()

        # Assert
        mock_create_client.assert_called_once_with('https://real.supabase.co', 'real_key')
        self.assertEqual(connection.client, mock_client)
        self.assertTrue(connection.is_connected())

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.core.db.database_init.load_dotenv')
    @patch('src.core.db.database_init.create_client')
    def test_initialization_github_actions_real_credentials(self, mock_create_client, mock_load_dotenv):
        """Test client initialization in GitHub Actions with real credentials."""
        # Arrange
        os.environ.update({
            'GITHUB_ACTIONS': 'true',
            'SUPABASE_URL': 'https://real.supabase.co',
            'SUPABASE_KEY': 'real_key'
        })
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Act
        connection = SupabaseConnection()

        # Assert
        mock_create_client.assert_called_once_with('https://real.supabase.co', 'real_key')
        self.assertEqual(connection.client, mock_client)
        self.assertTrue(connection.is_connected())

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.core.db.database_init.load_dotenv')
    @patch('src.core.db.database_init.create_client')
    def test_ci_with_test_credentials_skips_initialization(self, mock_create_client, mock_load_dotenv):
        """Test that CI with test credentials skips client initialization."""
        # Arrange
        os.environ.update({
            'CI': 'true',
            'SUPABASE_URL': 'https://test.supabase.co',
            'SUPABASE_KEY': 'test-key'
        })

        # Act
        connection = SupabaseConnection()

        # Assert
        mock_create_client.assert_not_called()
        self.assertIsNone(connection.client)
        self.assertFalse(connection.is_connected())

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.core.db.database_init.load_dotenv')
    @patch('src.core.db.database_init.create_client')
    def test_initialization_failure_logs_warning(self, mock_create_client, mock_load_dotenv):
        """Test that initialization failures are logged as warnings."""
        # Arrange
        os.environ.update({
            'SUPABASE_URL': 'https://test.supabase.co',
            'SUPABASE_KEY': 'test_key'
        })
        mock_create_client.side_effect = Exception("Connection failed")

        with self.assertLogs('src.core.db.database_init', level='WARNING') as log:
            # Act
            connection = SupabaseConnection()

            # Assert
            self.assertIsNone(connection.client)
            self.assertFalse(connection.is_connected())
            self.assertTrue(any("Failed to initialize Supabase client" in message for message in log.output))

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.core.db.database_init.load_dotenv')
    @patch('src.core.db.database_init.create_client')
    def test_ci_initialization_failure_logs_warning(self, mock_create_client, mock_load_dotenv):
        """Test that CI initialization failures are logged as warnings."""
        # Arrange
        os.environ.update({
            'CI': 'true',
            'SUPABASE_URL': 'https://real.supabase.co',
            'SUPABASE_KEY': 'real_key'
        })
        mock_create_client.side_effect = Exception("CI connection failed")

        with self.assertLogs('src.core.db.database_init', level='WARNING') as log:
            # Act
            connection = SupabaseConnection()

            # Assert
            self.assertIsNone(connection.client)
            self.assertFalse(connection.is_connected())
            self.assertTrue(any("Failed to initialize Supabase client in CI" in message for message in log.output))

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.core.db.database_init.load_dotenv')
    @patch('src.core.db.database_init.sys.exit')
    def test_missing_credentials_non_ci_exits(self, mock_exit, mock_load_dotenv):
        """Test that missing credentials in non-CI environment causes exit."""
        # Arrange - no environment variables set

        # Act
        SupabaseConnection()

        # Assert
        mock_exit.assert_called_once_with(1)

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.core.db.database_init.load_dotenv')
    @patch('src.core.db.database_init.sys.exit')
    def test_missing_url_non_ci_exits(self, mock_exit, mock_load_dotenv):
        """Test that missing URL in non-CI environment causes exit."""
        # Arrange
        os.environ.update({
            'SUPABASE_KEY': 'test_key'
        })

        # Act
        SupabaseConnection()

        # Assert
        mock_exit.assert_called_once_with(1)

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.core.db.database_init.load_dotenv')
    @patch('src.core.db.database_init.sys.exit')
    def test_missing_key_non_ci_exits(self, mock_exit, mock_load_dotenv):
        """Test that missing key in non-CI environment causes exit."""
        # Arrange
        os.environ.update({
            'SUPABASE_URL': 'https://test.supabase.co'
        })

        # Act
        SupabaseConnection()

        # Assert
        mock_exit.assert_called_once_with(1)

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.core.db.database_init.load_dotenv')
    @patch('src.core.db.database_init.sys.exit')
    def test_missing_credentials_ci_logs_warning(self, mock_exit, mock_load_dotenv):
        """Test that missing credentials in CI environment logs warning but doesn't exit."""
        # Arrange
        os.environ.update({
            'CI': 'true'
        })

        with self.assertLogs('src.core.db.database_init', level='WARNING') as log:
            # Act
            connection = SupabaseConnection()

            # Assert
            mock_exit.assert_not_called()
            self.assertIsNone(connection.client)
            self.assertFalse(connection.is_connected())
            self.assertTrue(any("Supabase credentials not available or in CI mode" in message for message in log.output))

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.core.db.database_init.load_dotenv')
    @patch('src.core.db.database_init.create_client')
    def test_client_initialization_only_once(self, mock_create_client, mock_load_dotenv):
        """Test that client is initialized only once even with multiple instances."""
        # Arrange
        os.environ.update({
            'SUPABASE_URL': 'https://test.supabase.co',
            'SUPABASE_KEY': 'test_key'
        })
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Act
        connection1 = SupabaseConnection()
        connection2 = SupabaseConnection()
        connection3 = SupabaseConnection()

        # Assert
        # create_client should only be called once despite multiple instances
        mock_create_client.assert_called_once()
        self.assertIs(connection1.client, connection2.client)
        self.assertIs(connection2.client, connection3.client)

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.core.db.database_init.load_dotenv')
    def test_various_ci_environment_variables(self, mock_load_dotenv):
        """Test detection of CI environment with various environment variables."""
        test_cases = [
            {'CI': 'true'},
            {'GITHUB_ACTIONS': 'true'},
            {'CI': 'true', 'GITHUB_ACTIONS': 'true'},
            {'CI': 'false'},  # Should be treated as non-CI
            {'GITHUB_ACTIONS': 'false'},  # Should be treated as non-CI
        ]

        for i, env_vars in enumerate(test_cases):
            with self.subTest(case=i, env_vars=env_vars):
                # Reset singleton for each test case
                SupabaseConnection._instance = None
                SupabaseConnection._client = None
                
                # Clear environment and set test case variables
                os.environ.clear()
                os.environ.update(env_vars)
                
                # Add minimal credentials for non-CI cases
                is_ci = env_vars.get('CI') == 'true' or env_vars.get('GITHUB_ACTIONS') == 'true'
                if not is_ci:
                    os.environ.update({
                        'SUPABASE_URL': 'https://test.supabase.co',
                        'SUPABASE_KEY': 'test_key'
                    })

                if is_ci:
                    with self.assertLogs('src.core.db.database_init', level='WARNING'):
                        connection = SupabaseConnection()
                        self.assertIsNone(connection.client)
                else:
                    with patch('src.core.db.database_init.create_client') as mock_create:
                        mock_create.return_value = MagicMock()
                        connection = SupabaseConnection()
                        self.assertIsNotNone(connection.client)


class TestGetSupabaseClient(unittest.TestCase):
    """Test cases for the get_supabase_client convenience function."""

    def setUp(self):
        """Reset the singleton instance before each test."""
        SupabaseConnection._instance = None
        SupabaseConnection._client = None

    def tearDown(self):
        """Clean up after each test."""
        SupabaseConnection._instance = None
        SupabaseConnection._client = None

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.core.db.database_init.load_dotenv')
    @patch('src.core.db.database_init.create_client')
    def test_get_supabase_client_returns_client(self, mock_create_client, mock_load_dotenv):
        """Test that get_supabase_client returns the singleton client."""
        # Arrange
        os.environ.update({
            'SUPABASE_URL': 'https://test.supabase.co',
            'SUPABASE_KEY': 'test_key'
        })
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Act
        client = get_supabase_client()

        # Assert
        self.assertEqual(client, mock_client)

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.core.db.database_init.load_dotenv')
    def test_get_supabase_client_returns_none_when_not_initialized(self, mock_load_dotenv):
        """Test that get_supabase_client returns None when client is not initialized."""
        # Arrange
        os.environ.update({
            'CI': 'true'
        })

        with self.assertLogs('src.core.db.database_init', level='WARNING'):
            # Act
            client = get_supabase_client()

            # Assert
            self.assertIsNone(client)

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.core.db.database_init.load_dotenv')
    @patch('src.core.db.database_init.create_client')
    def test_get_supabase_client_multiple_calls_same_instance(self, mock_create_client, mock_load_dotenv):
        """Test that multiple calls to get_supabase_client return the same instance."""
        # Arrange
        os.environ.update({
            'SUPABASE_URL': 'https://test.supabase.co',
            'SUPABASE_KEY': 'test_key'
        })
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Act
        client1 = get_supabase_client()
        client2 = get_supabase_client()
        client3 = get_supabase_client()

        # Assert
        self.assertIs(client1, client2)
        self.assertIs(client2, client3)
        # Should only create client once
        mock_create_client.assert_called_once()


class TestLoggingBehavior(unittest.TestCase):
    """Test cases for logging behavior in different scenarios."""

    def setUp(self):
        """Reset the singleton instance before each test."""
        SupabaseConnection._instance = None
        SupabaseConnection._client = None

    def tearDown(self):
        """Clean up after each test."""
        SupabaseConnection._instance = None
        SupabaseConnection._client = None

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.core.db.database_init.load_dotenv')
    @patch('src.core.db.database_init.create_client')
    def test_successful_initialization_logs_info(self, mock_create_client, mock_load_dotenv):
        """Test that successful initialization logs info message."""
        # Arrange
        os.environ.update({
            'SUPABASE_URL': 'https://test.supabase.co',
            'SUPABASE_KEY': 'test_key'
        })
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        with self.assertLogs('src.core.db.database_init', level='INFO') as log:
            # Act
            SupabaseConnection()

            # Assert
            self.assertTrue(any("Supabase client initialized successfully" in message for message in log.output))

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.core.db.database_init.load_dotenv')
    @patch('src.core.db.database_init.create_client')
    def test_ci_successful_initialization_logs_info(self, mock_create_client, mock_load_dotenv):
        """Test that successful CI initialization logs info message."""
        # Arrange
        os.environ.update({
            'CI': 'true',
            'SUPABASE_URL': 'https://real.supabase.co',
            'SUPABASE_KEY': 'real_key'
        })
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        with self.assertLogs('src.core.db.database_init', level='INFO') as log:
            # Act
            SupabaseConnection()

            # Assert
            self.assertTrue(any("Supabase client initialized in CI environment" in message for message in log.output))

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.core.db.database_init.load_dotenv')
    def test_missing_credentials_logs_error(self, mock_load_dotenv):
        """Test that missing credentials logs error message."""
        # Arrange - no credentials set

        with patch('src.core.db.database_init.sys.exit'):
            with self.assertLogs('src.core.db.database_init', level='ERROR') as log:
                # Act
                SupabaseConnection()

                # Assert
                self.assertTrue(any("SUPABASE_URL and/or SUPABASE_KEY environment variables are not set" in message for message in log.output))


if __name__ == '__main__':
    unittest.main()
