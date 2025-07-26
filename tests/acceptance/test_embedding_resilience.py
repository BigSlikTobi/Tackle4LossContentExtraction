import unittest
from unittest.mock import patch, MagicMock, call
import sys
import os
import logging

# Adjust path to import module from the project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

# Modules to be tested or that contain components to be mocked
# Note: The client name in create_embeddings is now openai_client_instance
from src.core.utils.create_embeddings import create_and_store_embedding, openai_client_instance
from openai import APIError, APIConnectionError # For simulating OpenAI errors

# Configure a simple logger for the test output (captures print statements from the module)
# This logger is for the test script's own high-level logging
acceptance_test_logger = logging.getLogger("AcceptanceTestLogger_Embedding")
acceptance_test_logger.setLevel(logging.INFO)
if not acceptance_test_logger.hasHandlers(): # Ensure handler is not added multiple times
    stream_handler = logging.StreamHandler(sys.stdout)
    acceptance_test_logger.addHandler(stream_handler)

# This will be the mock for the logger inside create_embeddings.py
mock_create_embeddings_logger = MagicMock(spec=logging.Logger)

class TestEmbeddingResilience(unittest.TestCase):

    def setUp(self):
        mock_create_embeddings_logger.reset_mock()
        # Sample articles
        self.sample_articles = [
            {"id": 1, "content": "This is a normal article content."},
            {"id": 2, "content": "This article will cause an OpenAI APIError."},
            {"id": 3, "content": "Another normal article."},
            {"id": 4, "content": "This one will also fail with OpenAI."},
        ]
        self.mock_successful_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]


    @patch('src.core.utils.create_embeddings.logger', mock_create_embeddings_logger) # Patch the logger in the CUT
    @patch('src.core.utils.create_embeddings.supabase_client', new_callable=MagicMock)
    @patch('src.core.utils.create_embeddings.openai_client_instance') # Patch the actual client instance used
    def test_openai_failures_are_handled(self, mock_actual_openai_client, mock_supabase_client_for_embeddings):
        # mock_actual_openai_client is the one used by create_embedding if not None
        # The logger is patched directly with mock_create_embeddings_logger and not passed as an argument.

        acceptance_test_logger.info("\n--- Scenario 1: OpenAI API Failure during Embedding Creation ---")

        # Ensure the client is not None for this test path, so create_embedding tries to use it.
        # If we wanted to test client being None, we'd patch openai_client_instance to None.
        # Here, we want to test its 'create' method failing.
        # So, mock_actual_openai_client should simulate a configured client.
        mock_actual_openai_client.api_key = "fake_key_for_test" # Ensure it passes the api_key check

        # This error will be raised by the 'embeddings.create' call
        simulated_error = APIConnectionError(message="Simulated OpenAI Connection Error", request=MagicMock())

        def openai_create_side_effect(*args, **kwargs):
            input_text = kwargs.get('input', '')
            if "OpenAI APIError" in input_text or "also fail with OpenAI" in input_text:
                raise simulated_error

            mock_embedding_response = MagicMock()
            mock_embedding_response.data = [MagicMock()]
            mock_embedding_response.data[0].embedding = self.mock_successful_embedding
            return mock_embedding_response

        # Configure the .create method on the (already mocked) openai_client_instance
        mock_actual_openai_client.embeddings.create.side_effect = openai_create_side_effect

        # Mock the store_embedding's Supabase call
        mock_supabase_insert_chain = MagicMock()
        mock_supabase_client_for_embeddings.table.return_value.insert.return_value = mock_supabase_insert_chain
        mock_supabase_insert_chain.execute.return_value = MagicMock(error=None)

        # --- Execution ---
        acceptance_test_logger.info("Processing articles for embedding and storage...")
        for article in self.sample_articles:
            acceptance_test_logger.info(f"Attempting to process article_id: {article['id']}")
            create_and_store_embedding(article_id=article['id'], content=article['content'])

        # --- Verification ---
        acceptance_test_logger.info("\nVerifying results...")

        # 1. Check logs for appropriate error messages (via mock_create_embeddings_logger)
        # create_embedding logs errors for API failures.
        # create_and_store_embedding logs info if embedding creation failed.

        # Expected error logs for article 2 and 4 from create_embedding
        # Format: logger.error("OpenAI APIError type for article_id %s: %s", article_id, e)
        # Expected info logs for article 2 and 4 from create_and_store_embedding
        # Format: logger.info("Embedding creation failed for article %s (see previous errors), skipping storage.", article_id)

        # Check calls to the logger injected into create_embeddings.py
        # Error calls from create_embedding
        mock_create_embeddings_logger.error.assert_any_call(
            "OpenAI APIConnectionError for article_id %s: %s", 2, simulated_error
        )
        mock_create_embeddings_logger.error.assert_any_call(
            "OpenAI APIConnectionError for article_id %s: %s", 4, simulated_error
        )
        # Info calls from create_and_store_embedding
        mock_create_embeddings_logger.info.assert_any_call(
            "Embedding creation failed for article %s (see previous errors), skipping storage.", 2
        )
        mock_create_embeddings_logger.info.assert_any_call(
            "Embedding creation failed for article %s (see previous errors), skipping storage.", 4
        )

        acceptance_test_logger.info("Verified: Error messages were logged for failed OpenAI calls.")

        # 2. Verify that embeddings are "stored" only for successful articles (1 and 3)
        successful_inserts_args = []
        for call_args_list_item in mock_supabase_client_for_embeddings.table.return_value.insert.call_args_list:
            data_inserted = call_args_list_item[0][0]
            successful_inserts_args.append(data_inserted['SourceArticle'])

        self.assertIn(1, successful_inserts_args, "Embedding for article 1 should have been stored.")
        self.assertIn(3, successful_inserts_args, "Embedding for article 3 should have been stored.")
        self.assertNotIn(2, successful_inserts_args, "Embedding for article 2 should NOT have been stored.")
        self.assertNotIn(4, successful_inserts_args, "Embedding for article 4 should NOT have been stored.")

        acceptance_test_logger.info("Verified: Embeddings stored correctly based on OpenAI success/failure.")

        # 3. The script completes without crashing (implicitly verified by test completion)
        acceptance_test_logger.info("Verified: Script completed without crashing.")
        acceptance_test_logger.info("--- Test Scenario 1 Complete ---")

if __name__ == '__main__':
    # This allows running the test directly.
    # In a real CI/CD, you'd use 'python -m unittest discover tests/acceptance'
    # For this conceptual test, direct execution is fine.
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestEmbeddingResilience)
    runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2)
    runner.run(suite)
