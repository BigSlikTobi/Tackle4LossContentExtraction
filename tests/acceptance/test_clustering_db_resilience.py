import unittest
from unittest.mock import patch, MagicMock, call
import numpy as np
import sys
import os
import logging

# Adjust path to import module from the project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

# Modules to be tested or that contain components to be mocked
from src.core.clustering.db_access import (
    fetch_unclustered_articles,
    assign_article_to_cluster,
    # sb as supabase_client_instance # Not needed if we patch 'src.core.clustering.db_access.sb'
)
from postgrest.exceptions import APIError # For simulating Supabase errors

# Configure a simple logger for the test output
test_logger = logging.getLogger("AcceptanceTestLogger_ClusteringDB")
test_logger.setLevel(logging.INFO)
stream_handler = logging.StreamHandler(sys.stdout)
test_logger.addHandler(stream_handler)

# Mock logger in db_access module
# This allows us to assert that logger.error was called within db_access functions
db_access_logger_mock = MagicMock(spec=logging.Logger)

@patch('src.core.clustering.db_access.logger', db_access_logger_mock) # Patch the logger inside db_access.py
class TestClusteringDbResilience(unittest.TestCase):

    def setUp(self):
        db_access_logger_mock.reset_mock()
        self.sample_articles_from_db = [
            (1, np.array([0.1, 0.2])), # (article_id, embedding)
            (2, np.array([0.3, 0.4])),
            (3, np.array([0.5, 0.6])),
        ]

    @patch('src.core.clustering.db_access.sb') # Mock the Supabase client 'sb' in db_access.py
    def test_db_failure_fetch_unclustered(self, mock_sb_client):
        test_logger.info("\n--- Scenario 3a: Supabase DB Failure during fetch_unclustered_articles ---")

        # Setup: Mock sb.table(...).select(...).execute() to raise APIError
        error_payload = {"message": "Simulated DB connection error during fetch"}
        mock_sb_client.table.return_value.select.return_value.is_.return_value.eq.return_value.order.return_value.limit.return_value.execute.side_effect = APIError(error_payload)

        # --- Execution ---
        test_logger.info("Attempting to fetch unclustered articles (expecting failure)...")
        articles = fetch_unclustered_articles()

        # --- Verification ---
        # 1. Check logs for appropriate error messages
        db_access_logger_mock.error.assert_called_once()
        logged_error_message = db_access_logger_mock.error.call_args[0][0]
        self.assertIn("Supabase APIError in fetch_unclustered_articles", logged_error_message)
        self.assertIn(str(error_payload), logged_error_message)
        test_logger.info(f"Verified: Error correctly logged: {logged_error_message}")

        # 2. Verify that the function returns an empty list
        self.assertEqual(articles, [])
        test_logger.info("Verified: fetch_unclustered_articles returned [] on DB error.")

        # 3. The script completes without crashing (implicitly verified by test completion)
        test_logger.info("Verified: Script completed without crashing.")
        test_logger.info("--- Test Scenario 3a Complete ---")


    @patch('src.core.clustering.db_access.sb') # Mock the Supabase client 'sb' in db_access.py
    def test_db_failure_assign_article_to_cluster(self, mock_sb_client):
        test_logger.info("\n--- Scenario 3b: Supabase DB Failure during assign_article_to_cluster ---")
        db_access_logger_mock.reset_mock() # Reset from previous test if any calls were made

        article_to_assign_id = 100
        target_cluster_id = "cluster_test_1"

        # Setup: Mock sb.table(...).update(...).execute() to raise APIError
        error_payload = {"message": "Simulated DB error during assignment"}
        mock_sb_client.table.return_value.update.return_value.eq.return_value.execute.side_effect = APIError(error_payload)

        # --- Execution ---
        # Simplified pipeline: fetch (mock success), attempt to assign (mock failure for one, success for another)
        # For this specific test, we just call assign_article_to_cluster directly.

        test_logger.info(f"Attempting to assign article {article_to_assign_id} (expecting failure)...")
        assign_article_to_cluster(article_id=article_to_assign_id, cluster_id=target_cluster_id)

        # --- Verification ---
        # 1. Check logs for appropriate error messages
        db_access_logger_mock.error.assert_called_once()
        logged_error_message = db_access_logger_mock.error.call_args[0][0]
        self.assertIn(f"Supabase APIError assigning article {article_to_assign_id} to cluster {target_cluster_id}", logged_error_message)
        self.assertIn(str(error_payload), logged_error_message)
        test_logger.info(f"Verified: Error correctly logged: {logged_error_message}")

        # 2. Verify that the pipeline would continue for other articles (conceptual)
        #    To simulate this, let's try assigning another article, this time mocking success
        db_access_logger_mock.reset_mock() # Reset logger for the next call
        mock_sb_client.table.return_value.update.return_value.eq.return_value.execute.side_effect = None # Clear previous side_effect
        mock_sb_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(error=None) # Mock success

        another_article_id = 101
        test_logger.info(f"Attempting to assign article {another_article_id} (expecting success)...")
        assign_article_to_cluster(article_id=another_article_id, cluster_id=target_cluster_id)

        db_access_logger_mock.error.assert_not_called() # No error for the second call
        # db_access_logger_mock.debug.assert_called() # Check for debug log of successful assignment
        test_logger.info(f"Verified: Subsequent assignment for article {another_article_id} was attempted (and would succeed).")

        # 3. The script completes without crashing (implicitly verified by test completion)
        test_logger.info("Verified: Script completed without crashing.")
        test_logger.info("--- Test Scenario 3b Complete ---")

if __name__ == '__main__':
    # For direct execution of this conceptual test script
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestClusteringDbResilience)
    runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2)
    runner.run(suite)
