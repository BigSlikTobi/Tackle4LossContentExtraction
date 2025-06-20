import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Adjust path to import module from parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import httpx # Import httpx for mocking request/response

from core.utils.create_embeddings import create_embedding, normalize_embedding, store_embedding, create_and_store_embedding
from openai import APIError, APITimeoutError, RateLimitError, APIConnectionError, APIStatusError
import numpy as np

# Mock the OpenAI client globally for all tests in this class
@patch('core.utils.create_embeddings.client')
class TestCreateEmbeddingFunction(unittest.TestCase):

    def test_create_embedding_success(self, mock_openai_client):
        """Test successful embedding creation."""
        mock_embedding_data = [0.1, 0.2, 0.3]
        mock_response = MagicMock()
        mock_response.data = [MagicMock()]
        mock_response.data[0].embedding = mock_embedding_data
        mock_openai_client.embeddings.create.return_value = mock_response

        embedding = create_embedding("test text", article_id=1)
        self.assertEqual(embedding, mock_embedding_data)
        mock_openai_client.embeddings.create.assert_called_once_with(
            model="text-embedding-3-small",
            input="test text",
            encoding_format="float"
        )

    @patch('builtins.print')
    def test_create_embedding_api_error(self, mock_print, mock_openai_client):
        """Test handling of OpenAI APIError."""
        mock_request = httpx.Request(method="POST", url="https://api.openai.com/v1/embeddings")
        # APIError base class might not use response directly in constructor; request and body are more common.
        mock_openai_client.embeddings.create.side_effect = APIError("Test API Error", request=mock_request, body=None)

        embedding = create_embedding("test text for api error", article_id=2)
        self.assertIsNone(embedding)
        mock_print.assert_called_with("OpenAI APIError: Test API Error for article_id: 2", file=sys.stderr)

    @patch('builtins.print')
    def test_create_embedding_timeout_error(self, mock_print, mock_openai_client):
        """Test handling of OpenAI APITimeoutError."""
        # APITimeoutError(message) - simplified
        mock_openai_client.embeddings.create.side_effect = APITimeoutError("Test Timeout Error")

        embedding = create_embedding("test text for timeout error", article_id=3)
        self.assertIsNone(embedding)
        mock_print.assert_called_with("OpenAI APITimeoutError: Request timed out. for article_id: 3", file=sys.stderr)

    @patch('builtins.print')
    def test_create_embedding_rate_limit_error(self, mock_print, mock_openai_client):
        """Test handling of OpenAI RateLimitError."""
        mock_request = httpx.Request(method="POST", url="https://api.openai.com/v1/embeddings")
        mock_response = httpx.Response(status_code=429, request=mock_request, content=b"Rate limit exceeded")
        # RateLimitError(message, response, body) - request comes from response
        mock_openai_client.embeddings.create.side_effect = RateLimitError("Test Rate Limit Error", response=mock_response, body=None)

        embedding = create_embedding("test text for rate limit error", article_id=4)
        self.assertIsNone(embedding)
        mock_print.assert_called_with("OpenAI RateLimitError: Test Rate Limit Error for article_id: 4", file=sys.stderr)

    @patch('builtins.print')
    def test_create_embedding_connection_error(self, mock_print, mock_openai_client):
        """Test handling of OpenAI APIConnectionError."""
        mock_request = httpx.Request(method="POST", url="https://api.openai.com/v1/embeddings")
        # APIConnectionError(message, request=request)
        mock_openai_client.embeddings.create.side_effect = APIConnectionError(message="Test Connection Error", request=mock_request)

        embedding = create_embedding("test text for connection error", article_id=5)
        self.assertIsNone(embedding)
        mock_print.assert_called_with("OpenAI APIConnectionError: Test Connection Error for article_id: 5", file=sys.stderr)

    @patch('builtins.print')
    def test_create_embedding_status_error(self, mock_print, mock_openai_client):
        """Test handling of OpenAI APIStatusError."""
        mock_request = httpx.Request(method="POST", url="https://api.openai.com/v1/embeddings")
        # Ensure the mocked response has a status code that would typically be an APIStatusError (e.g., 400, 401, 403, etc.)
        # and has 'request' attribute
        mock_response = httpx.Response(status_code=400, request=mock_request, content=b"Bad Request")

        # The APIStatusError constructor expects 'response' and 'body' (optional), and 'request' implicitly from response
        mock_openai_client.embeddings.create.side_effect = APIStatusError("Test Status Error", response=mock_response, body=None)

        embedding = create_embedding("test text for status error", article_id=6)
        self.assertIsNone(embedding)
        # The __str__ of APIStatusError includes the status code, so the error message in the code might be different
        # For now, let's assume the generic "OpenAI APIStatusError: ..." message as per current code.
        # If the actual error message in code changes to be more specific, this assertion will need an update.
        # The key is that it's caught by the APIStatusError handler.
        # The print statement in the actual code is: print(f"OpenAI APIStatusError: {e}"...)
        # The string representation of e (the error instance) will be "Test Status Error"
        mock_print.assert_called_with("OpenAI APIStatusError: Test Status Error for article_id: 6", file=sys.stderr)


    @patch('builtins.print')
    def test_create_embedding_unexpected_openai_error(self, mock_print, mock_openai_client):
        """Test handling of a generic Exception from OpenAI client."""
        mock_openai_client.embeddings.create.side_effect = Exception("Unexpected test error")

        embedding = create_embedding("test text for unexpected error", article_id=7)
        self.assertIsNone(embedding)
        mock_print.assert_called_with("Unexpected error: Unexpected test error for article_id: 7", file=sys.stderr)


class TestNormalizeEmbeddingFunction(unittest.TestCase):
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


@patch('core.utils.create_embeddings.supabase_client')
class TestStoreEmbeddingFunction(unittest.TestCase):

    def test_store_embedding_success(self, mock_supabase_client):
        """Test successful storage of an embedding."""
        mock_insert_builder = MagicMock()
        mock_supabase_client.table.return_value.insert.return_value = mock_insert_builder
        # mock_insert_builder.execute.return_value = MagicMock() # No need to mock execute if not checking its response

        article_id = 10
        embedding = [0.1, 0.2, 0.3]

        with patch('builtins.print') as mock_print: # Capture print output
            store_embedding(article_id, embedding)

        mock_supabase_client.table.assert_called_once_with("ArticleVector")
        mock_supabase_client.table.return_value.insert.assert_called_once_with({
            "embedding": embedding,
            "SourceArticle": article_id
        })
        mock_insert_builder.execute.assert_called_once()
        mock_print.assert_called_with(f"Successfully stored embedding for article {article_id}")

    @patch('builtins.print')
    def test_store_embedding_db_error(self, mock_print, mock_supabase_client):
        """Test handling of a database error during storage."""
        mock_insert_builder = MagicMock()
        mock_supabase_client.table.return_value.insert.return_value = mock_insert_builder
        mock_insert_builder.execute.side_effect = Exception("DB Test Error")

        article_id = 11
        embedding = [0.4, 0.5, 0.6]

        store_embedding(article_id, embedding)

        mock_supabase_client.table.assert_called_once_with("ArticleVector")
        mock_supabase_client.table.return_value.insert.assert_called_once_with({
            "embedding": embedding,
            "SourceArticle": article_id
        })
        mock_insert_builder.execute.assert_called_once()
        mock_print.assert_called_with(f"Error storing embedding for article_id {article_id}: DB Test Error", file=sys.stderr)


@patch('core.utils.create_embeddings.store_embedding')
@patch('core.utils.create_embeddings.normalize_embedding')
@patch('core.utils.create_embeddings.create_embedding')
class TestCreateAndStoreEmbeddingFunction(unittest.TestCase):

    def test_create_and_store_embedding_success(self, mock_create_embedding, mock_normalize_embedding, mock_store_embedding):
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
        mock_store_embedding.assert_called_once_with(article_id, normalized_embedding)

    @patch('builtins.print')
    def test_create_and_store_embedding_creation_fails(self, mock_print, mock_create_embedding, mock_normalize_embedding, mock_store_embedding):
        """Test that store_embedding is not called if create_embedding returns None."""
        article_id = 21
        content = "Test content where embedding creation fails"

        mock_create_embedding.return_value = None
        # mock_normalize_embedding and mock_store_embedding are already mocks

        create_and_store_embedding(article_id, content)

        mock_create_embedding.assert_called_once_with(content, article_id=article_id)
        mock_normalize_embedding.assert_not_called()
        mock_store_embedding.assert_not_called()
        mock_print.assert_called_with(f"Embedding creation failed for article {article_id}, skipping storage.", file=sys.stderr)

    @patch('builtins.print')
    def test_create_and_store_embedding_normalization_fails(self, mock_print, mock_create_embedding, mock_normalize_embedding, mock_store_embedding):
        """Test error handling if normalize_embedding fails."""
        article_id = 22
        content = "Test content where normalization fails"
        raw_embedding = [0.1, 0.2, 0.3]

        mock_create_embedding.return_value = raw_embedding
        mock_normalize_embedding.side_effect = Exception("Normalization Test Error")
        # mock_store_embedding is already a mock

        create_and_store_embedding(article_id, content)

        mock_create_embedding.assert_called_once_with(content, article_id=article_id)
        mock_normalize_embedding.assert_called_once_with(raw_embedding)
        mock_store_embedding.assert_not_called()
        mock_print.assert_called_with(f"Error in create_and_store_embedding for article {article_id}: Normalization Test Error", file=sys.stderr)


if __name__ == '__main__':
    unittest.main()
