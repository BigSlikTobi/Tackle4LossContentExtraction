import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Adjust path to import module from parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import httpx # Import httpx for mocking request/response

from core.utils.create_embeddings import create_embedding, normalize_embedding, store_embedding, create_and_store_embedding
from openai import APIError, APITimeoutError, RateLimitError, APIConnectionError, APIStatusError
import numpy as np
import logging # Import logging for logger type hint if needed

# Mock the logger used in the module.
# We are patching 'core.utils.create_embeddings.logger' which is the logger instance.
mock_module_logger = MagicMock(spec=logging.Logger)

# Mock the OpenAI client instance globally for relevant tests
@patch('core.utils.create_embeddings.logger', mock_module_logger)
@patch('core.utils.create_embeddings.openai_client_instance')
class TestCreateEmbeddingFunction(unittest.TestCase):

    def setUp(self):
        mock_module_logger.reset_mock()

    def test_create_embedding_success(self, mock_openai_client_instance):
        """Test successful embedding creation."""
        mock_embedding_data = [0.1, 0.2, 0.3]
        mock_response = MagicMock()
        mock_response.data = [MagicMock()]
        mock_response.data[0].embedding = mock_embedding_data
        mock_openai_client_instance.embeddings.create.return_value = mock_response

        embedding = create_embedding("test text", article_id=1)
        self.assertEqual(embedding, mock_embedding_data)
        mock_openai_client_instance.embeddings.create.assert_called_once_with(
            model="text-embedding-3-small",
            input="test text",
            encoding_format="float"
        )
        mock_module_logger.error.assert_not_called()

    def test_create_embedding_openai_client_none(self, mock_openai_client_instance):
        """Test create_embedding when openai_client_instance is None."""
        with patch('core.utils.create_embeddings.openai_client_instance', None):
            embedding = create_embedding("test text", article_id=100)
            self.assertIsNone(embedding)
            mock_module_logger.error.assert_called_once_with(
                "OpenAI client is not initialized (likely missing API key). Cannot create embedding for article_id: %s.", 100
            )

    def test_create_embedding_openai_client_no_api_key(self, mock_openai_client_instance):
        """Test create_embedding when openai_client_instance.api_key is None."""
        # Mock the client instance itself to simulate no api_key after initialization
        mock_configured_client = MagicMock()
        mock_configured_client.api_key = None # Simulate missing API key
        # mock_openai_client_instance is already a mock passed to the test method by @patch
        # We change its behavior for this test or repatch it locally.
        with patch('core.utils.create_embeddings.openai_client_instance', mock_configured_client):
            embedding = create_embedding("test text", article_id=101)
            self.assertIsNone(embedding)
            mock_module_logger.error.assert_called_once_with(
                "OpenAI client is not configured with an API key. Cannot create embedding for article_id: %s.", 101
            )

    def test_create_embedding_api_error(self, mock_openai_client_instance):
        """Test handling of OpenAI APIError."""
        mock_request = httpx.Request(method="POST", url="https://api.openai.com/v1/embeddings")
        error_instance = APIError("Test API Error", request=mock_request, body=None)
        mock_openai_client_instance.embeddings.create.side_effect = error_instance

        embedding = create_embedding("test text for api error", article_id=2)
        self.assertIsNone(embedding)
        mock_module_logger.error.assert_called_once_with(
            "OpenAI APIError (e.g. 5xx) for article_id %s: %s", 2, error_instance
        )

    def test_create_embedding_timeout_error(self, mock_openai_client_instance):
        """Test handling of OpenAI APITimeoutError."""
        error_instance = APITimeoutError("Test Timeout Error") # Request is optional
        mock_openai_client_instance.embeddings.create.side_effect = error_instance

        embedding = create_embedding("test text for timeout error", article_id=3)
        self.assertIsNone(embedding)
        mock_module_logger.error.assert_called_once_with(
            "OpenAI APITimeoutError for article_id %s: %s", 3, error_instance
        )

    def test_create_embedding_rate_limit_error(self, mock_openai_client_instance):
        """Test handling of OpenAI RateLimitError."""
        mock_request = httpx.Request(method="POST", url="https://api.openai.com/v1/embeddings")
        mock_response = httpx.Response(status_code=429, request=mock_request, content=b"Rate limit exceeded")
        error_instance = RateLimitError("Test Rate Limit Error", response=mock_response, body=None)
        mock_openai_client_instance.embeddings.create.side_effect = error_instance

        embedding = create_embedding("test text for rate limit error", article_id=4)
        self.assertIsNone(embedding)
        mock_module_logger.error.assert_called_once_with(
            "OpenAI RateLimitError for article_id %s: %s", 4, error_instance
        )

    def test_create_embedding_connection_error(self, mock_openai_client_instance):
        """Test handling of OpenAI APIConnectionError."""
        mock_request = httpx.Request(method="POST", url="https://api.openai.com/v1/embeddings")
        error_instance = APIConnectionError(message="Test Connection Error", request=mock_request)
        mock_openai_client_instance.embeddings.create.side_effect = error_instance

        embedding = create_embedding("test text for connection error", article_id=5)
        self.assertIsNone(embedding)
        mock_module_logger.error.assert_called_once_with(
            "OpenAI APIConnectionError for article_id %s: %s", 5, error_instance
        )

    def test_create_embedding_status_error(self, mock_openai_client_instance):
        """Test handling of OpenAI APIStatusError."""
        mock_request = httpx.Request(method="POST", url="https://api.openai.com/v1/embeddings")
        # Ensure the mocked response has a status code that would typically be an APIStatusError (e.g., 400, 401, 403, etc.)
        # and has 'request' attribute
        mock_response = httpx.Response(status_code=400, request=mock_request, content=b"Bad Request")

        # The APIStatusError constructor expects 'response' and 'body' (optional), and 'request' implicitly from response
        error_instance = APIStatusError("Test Status Error", response=mock_response, body=None)
        mock_openai_client_instance.embeddings.create.side_effect = error_instance

        embedding = create_embedding("test text for status error", article_id=6)
        self.assertIsNone(embedding)
        mock_module_logger.error.assert_called_once_with(
            "OpenAI APIStatusError (e.g. 4xx) for article_id %s: %s", 6, error_instance
        )

    def test_create_embedding_unexpected_error(self, mock_openai_client_instance):
        """Test handling of a generic Exception from OpenAI client call."""
        error_instance = Exception("Unexpected test error")
        mock_openai_client_instance.embeddings.create.side_effect = error_instance

        embedding = create_embedding("test text for unexpected error", article_id=7)
        self.assertIsNone(embedding)
        mock_module_logger.error.assert_called_once_with(
            "Unexpected error during embedding creation for article_id %s: %s", 7, error_instance, exc_info=True
        )

@patch('core.utils.create_embeddings.logger', mock_module_logger) # Patch logger for this class too
class TestNormalizeEmbeddingFunction(unittest.TestCase):
    def setUp(self):
        mock_module_logger.reset_mock()

    def test_normalize_embedding_non_zero_norm(self):
        embedding = [1.0, 2.0, 2.0] # Norm is 3
        normalized = normalize_embedding(embedding)
        expected = [1/3, 2/3, 2/3]
        np.testing.assert_array_almost_equal(normalized, expected)

    def test_normalize_embedding_zero_vector(self):
        embedding = [0.0, 0.0, 0.0]
        normalized = normalize_embedding(embedding)
        expected = [0.0, 0.0, 0.0]
        np.testing.assert_array_almost_equal(normalized, expected)

    def test_normalize_embedding_already_normalized(self):
        embedding = [1/np.sqrt(3), 1/np.sqrt(3), 1/np.sqrt(3)]
        normalized = normalize_embedding(embedding)
        expected = [1/np.sqrt(3), 1/np.sqrt(3), 1/np.sqrt(3)]
        np.testing.assert_array_almost_equal(normalized, expected)



@patch('core.utils.create_embeddings.logger', mock_module_logger)
@patch('core.utils.create_embeddings.supabase_client')
class TestStoreEmbeddingFunction(unittest.TestCase):

    def setUp(self):
        mock_module_logger.reset_mock()

    def test_store_embedding_success(self, mock_supabase_client_instance):
        """Test successful storage of an embedding."""
        mock_insert_builder = MagicMock()
        mock_supabase_client_instance.table.return_value.insert.return_value = mock_insert_builder

        article_id = 10
        embedding = [0.1, 0.2, 0.3]

        store_embedding(article_id, embedding)

        mock_supabase_client_instance.table.assert_called_once_with("ArticleVector")
        mock_supabase_client_instance.table.return_value.insert.assert_called_once_with({
            "embedding": embedding,
            "SourceArticle": article_id
        })
        mock_insert_builder.execute.assert_called_once()
        mock_module_logger.info.assert_called_once_with("Successfully stored embedding for article %s", article_id)
        mock_module_logger.error.assert_not_called()

    def test_store_embedding_supabase_client_none(self, mock_supabase_client_instance):
        """Test store_embedding when supabase_client is None."""
        # We patch supabase_client at the module level for this test's scope
        with patch('core.utils.create_embeddings.supabase_client', None):
            store_embedding(111, [0.1,0.2])
            # In CI, we expect a warning, not an error.
            if os.getenv("CI") == 'true' or os.getenv("GITHUB_ACTIONS") == 'true':
                mock_module_logger.warning.assert_called_once_with(
                    "Supabase client not initialized in CI. Skipping embedding storage for article_id %s.", 111
                )
            else:
                mock_module_logger.error.assert_called_once_with(
                    "Supabase client not initialized. Cannot store embedding for article_id %s.", 111
                )

    def test_store_embedding_db_error(self, mock_supabase_client_instance):
        """Test handling of a database error during storage."""
        mock_insert_builder = MagicMock()
        mock_supabase_client_instance.table.return_value.insert.return_value = mock_insert_builder
        error_instance = Exception("DB Test Error")
        mock_insert_builder.execute.side_effect = error_instance

        article_id = 11
        embedding = [0.4, 0.5, 0.6]

        store_embedding(article_id, embedding)

        mock_supabase_client_instance.table.assert_called_once_with("ArticleVector")
        mock_supabase_client_instance.table.return_value.insert.assert_called_once_with({
            "embedding": embedding,
            "SourceArticle": article_id
        })
        mock_insert_builder.execute.assert_called_once()
        mock_module_logger.error.assert_called_once_with(
            "Error storing embedding for article_id %s: %s", article_id, error_instance, exc_info=True
        )

@patch('core.utils.create_embeddings.logger', mock_module_logger)
@patch('core.utils.create_embeddings.store_embedding')
@patch('core.utils.create_embeddings.normalize_embedding')
@patch('core.utils.create_embeddings.create_embedding')
class TestCreateAndStoreEmbeddingFunction(unittest.TestCase):
    def setUp(self):
        mock_module_logger.reset_mock()

    def test_create_and_store_embedding_success(self, mock_create_embedding, mock_normalize_embedding, mock_store_embedding_func):
        """Test successful creation and storage of an embedding."""
        article_id = 20
        content = "Test content for end-to-end success"
        raw_embedding = [0.1, 0.2, 0.3]
        normalized_embedding = [0.18257418583505536, 0.3651483716701107, 0.5477225575051661] # Example normalized

        mock_create_embedding.return_value = raw_embedding
        mock_normalize_embedding.return_value = normalized_embedding
        # mock_store_embedding is already a mock

        create_and_store_embedding(article_id, content)

        mock_create_embedding.assert_called_once_with(content, article_id=article_id)
        mock_normalize_embedding.assert_called_once_with(raw_embedding)
        mock_store_embedding_func.assert_called_once_with(article_id, normalized_embedding)
        mock_module_logger.error.assert_not_called() # No errors in this path
        mock_module_logger.info.assert_not_called() # No info log for skipping in success path

    def test_create_and_store_embedding_creation_fails(self, mock_create_embedding, mock_normalize_embedding, mock_store_embedding_func):
        """Test that store_embedding is not called if create_embedding returns None."""
        article_id = 21
        content = "Test content where embedding creation fails"

        mock_create_embedding.return_value = None

        create_and_store_embedding(article_id, content)

        mock_create_embedding.assert_called_once_with(content, article_id=article_id)
        mock_normalize_embedding.assert_not_called()
        mock_store_embedding_func.assert_not_called()
        # Check for the info log about skipping storage
        mock_module_logger.info.assert_called_once_with(
            "Embedding creation failed for article %s (see previous errors), skipping storage.", article_id
        )

    def test_create_and_store_embedding_normalization_fails(self, mock_create_embedding, mock_normalize_embedding, mock_store_embedding_func):
        """Test error handling if normalize_embedding fails."""
        article_id = 22
        content = "Test content where normalization fails"
        raw_embedding = [0.1, 0.2, 0.3]
        error_instance = Exception("Normalization Test Error")

        mock_create_embedding.return_value = raw_embedding
        mock_normalize_embedding.side_effect = error_instance

        create_and_store_embedding(article_id, content)

        mock_create_embedding.assert_called_once_with(content, article_id=article_id)
        mock_normalize_embedding.assert_called_once_with(raw_embedding)
        mock_store_embedding_func.assert_not_called()
        mock_module_logger.error.assert_called_once_with(
            "Error during embedding normalization or dispatching to storage for article %s: %s",
            article_id,
            error_instance,
            exc_info=True
        )


if __name__ == '__main__':
    unittest.main()
