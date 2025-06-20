import unittest
from unittest.mock import patch, MagicMock, call
import sys
import os
import logging

# Adjust path to import module from the project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Modules to be tested or that contain components to be mocked
from core.utils.create_embeddings import create_and_store_embedding, client as openai_client_instance, supabase_client as embeddings_supabase_client
from openai import APIError # For simulating OpenAI errors

# Configure a simple logger for the test output (captures print statements from the module)
test_logger = logging.getLogger("AcceptanceTestLogger_Embedding")
test_logger.setLevel(logging.INFO)
stream_handler = logging.StreamHandler(sys.stdout)
test_logger.addHandler(stream_handler)

# Replace print with test_logger.info for capturing output from the module if necessary
# This is tricky because create_embeddings.py uses print to sys.stderr.
# For simplicity, we'll rely on unittest.mock.patch for specific print calls if needed,
# or manually inspect stderr for this conceptual test.

class TestEmbeddingResilience(unittest.TestCase):

    def setUp(self):
        # Sample articles
        self.sample_articles = [
            {"id": 1, "content": "This is a normal article content."},
            {"id": 2, "content": "This article will cause an OpenAI APIError."},
            {"id": 3, "content": "Another normal article."},
            {"id": 4, "content": "This one will also fail with OpenAI."},
        ]
        self.mock_successful_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

        # This will hold our "stored" embeddings
        self.mock_db_storage = {}

    @patch('core.utils.create_embeddings.supabase_client', new_callable=MagicMock) # Mock Supabase client in create_embeddings
    @patch.object(openai_client_instance.embeddings, 'create') # Mock openai.Client.embeddings.create
    @patch('builtins.print') # Mock print to check log messages
    def test_openai_failures_are_handled(self, mock_builtin_print, mock_openai_create, mock_supabase_client_for_embeddings):
        test_logger.info("\n--- Scenario 1: OpenAI API Failure during Embedding Creation ---")

        def openai_create_side_effect(*args, **kwargs):
            input_text = kwargs.get('input', '')
            if "OpenAI APIError" in input_text or "also fail with OpenAI" in input_text:
                # Simulate an APIError. The actual error structure might be more complex.
                # The 'create_embedding' function expects specific error types.
                # We use APIError as a general one here.
                raise APIError(message="Simulated OpenAI API Error", request=MagicMock(), body=None) # Adjusted for openai v1.x

            # Simulate successful response
            mock_embedding_response = MagicMock()
            mock_embedding_response.data = [MagicMock()]
            mock_embedding_response.data[0].embedding = self.mock_successful_embedding
            return mock_embedding_response

        mock_openai_create.side_effect = openai_create_side_effect

        # Mock the store_embedding's Supabase call
        # store_embedding uses: supabase_client.table("ArticleVector").insert(data).execute()
        mock_supabase_insert_chain = MagicMock()
        mock_supabase_client_for_embeddings.table.return_value.insert.return_value = mock_supabase_insert_chain
        mock_supabase_insert_chain.execute.return_value = MagicMock(error=None) # Simulate success

        # --- Execution ---
        test_logger.info("Processing articles for embedding and storage...")
        for article in self.sample_articles:
            test_logger.info(f"Attempting to process article_id: {article['id']}")
            # In a real pipeline, this might be an async call or part of a larger workflow
            create_and_store_embedding(article_id=article['id'], content=article['content'])

        # --- Verification ---
        test_logger.info("\nVerifying results...")

        # 1. Check logs for appropriate error messages (via mocked print)
        #    create_embedding prints to sys.stderr, create_and_store_embedding prints to sys.stderr for failures
        #    store_embedding prints to stdout for success, sys.stderr for failure.

        # Expected error logs for article 2 and 4
        # Format: "OpenAI APIError: Simulated OpenAI API Error for article_id: X"
        # Format: "Embedding creation failed for article X, skipping storage."

        # Let's check for specific print calls to stderr
        stderr_calls = [
            args[0] for call_args in mock_builtin_print.call_args_list
            if isinstance(call_args[0], tuple) and len(call_args[0]) > 0 and call_args[1].get('file') == sys.stderr
        ]

        self.assertTrue(any(f"OpenAI APIError: Simulated OpenAI API Error for article_id: 2" in log for log in stderr_calls))
        self.assertTrue(any(f"Embedding creation failed for article 2, skipping storage." in log for log in stderr_calls))
        self.assertTrue(any(f"OpenAI APIError: Simulated OpenAI API Error for article_id: 4" in log for log in stderr_calls))
        self.assertTrue(any(f"Embedding creation failed for article 4, skipping storage." in log for log in stderr_calls))

        test_logger.info("Verified: Error messages were logged for failed OpenAI calls.")

        # 2. Verify that embeddings are "stored" only for successful articles (1 and 3)
        # We check if the insert execute was called for the successful ones.
        # store_embedding calls supabase_client.table("ArticleVector").insert(data).execute()

        successful_inserts_args = []
        for call_args in mock_supabase_client_for_embeddings.table.return_value.insert.call_args_list:
            data_inserted = call_args[0][0] # data is the first positional arg to insert()
            successful_inserts_args.append(data_inserted['SourceArticle'])

        self.assertIn(1, successful_inserts_args, "Embedding for article 1 should have been stored.")
        self.assertIn(3, successful_inserts_args, "Embedding for article 3 should have been stored.")
        self.assertNotIn(2, successful_inserts_args, "Embedding for article 2 should NOT have been stored.")
        self.assertNotIn(4, successful_inserts_args, "Embedding for article 4 should NOT have been stored.")

        test_logger.info("Verified: Embeddings stored correctly based on OpenAI success/failure.")

        # 3. The script completes without crashing (implicitly verified by test completion)
        test_logger.info("Verified: Script completed without crashing.")
        test_logger.info("--- Test Scenario 1 Complete ---")

if __name__ == '__main__':
    # This allows running the test directly.
    # In a real CI/CD, you'd use 'python -m unittest discover tests/acceptance'
    # For this conceptual test, direct execution is fine.
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestEmbeddingResilience)
    runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2) # Ensure output goes to stdout
    runner.run(suite)
