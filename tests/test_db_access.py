import unittest
from unittest.mock import MagicMock, patch, call
import numpy as np
import sys
import os
import logging
from datetime import datetime, timedelta

# Adjust path to import module from parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import functions to be tested
from core.clustering.db_access import (
    fetch_unclustered_articles,
    fetch_existing_clusters,
    update_cluster_in_db,
    create_cluster_in_db,
    assign_article_to_cluster,
    batch_assign_articles_to_cluster,
    repair_zero_centroid_clusters,
    recalculate_cluster_member_counts,
    update_old_clusters_status,
    # sb as supabase_client_instance # For patching sb directly if needed for all tests
)

# Import APIError for simulating postgrest errors
from postgrest.exceptions import APIError


# Mock the logger used in db_access module
# We patch 'core.clustering.db_access.logger'
mock_logger = MagicMock(spec=logging.Logger)

# Mock the Supabase client instance 'sb' used in db_access.py
# All test methods will need to patch 'core.clustering.db_access.sb'
# or we can patch it at the class level if all tests use the same basic mock structure.

class TestDbAccess(unittest.TestCase):

    # The helper _create_mock_supabase_client_with_execute was not used, removing it.
    # Direct mocking of chains specific to each test proved more effective.

    @patch('core.clustering.db_access.logger', mock_logger)
    @patch('core.clustering.db_access.sb')
    def test_fetch_unclustered_articles_success(self, mock_sb):
        mock_logger.reset_mock()
        mock_data = [
            {"id": 1, "ArticleVector": [{"embedding": "[0.1,0.2]"}]},
            {"id": 2, "ArticleVector": [{"embedding": "[0.3,0.4]"}]},
        ]
        # Configure the mock chain for this specific test
        mock_sb.table.return_value.select.return_value.is_.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=mock_data, error=None)

        articles = fetch_unclustered_articles()
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0][0], 1)
        np.testing.assert_array_almost_equal(articles[0][1], np.array([0.1, 0.2]))
        mock_logger.error.assert_not_called()

    @patch('core.clustering.db_access.logger', mock_logger)
    @patch('core.clustering.db_access.sb')
    def test_fetch_unclustered_articles_api_error(self, mock_sb):
        mock_logger.reset_mock()
        error_dict = {"message": "DB down"}
        mock_sb.table.return_value.select.return_value.is_.return_value.eq.return_value.order.return_value.limit.return_value.execute.side_effect = APIError(error_dict)

        articles = fetch_unclustered_articles()
        self.assertEqual(articles, [])
        mock_logger.error.assert_called_once_with(f"Supabase APIError in fetch_unclustered_articles: {error_dict}")

    @patch('core.clustering.db_access.logger', mock_logger)
    @patch('core.clustering.db_access.sb')
    def test_fetch_unclustered_articles_generic_error(self, mock_sb):
        mock_logger.reset_mock()
        mock_sb.table.return_value.select.return_value.is_.return_value.eq.return_value.order.return_value.limit.return_value.execute.side_effect = Exception("Unexpected")

        articles = fetch_unclustered_articles()
        self.assertEqual(articles, [])
        mock_logger.error.assert_called_once_with("Unexpected error in fetch_unclustered_articles: Unexpected")

    @patch('core.clustering.db_access.logger') # Let patch create the mock
    def test_fetch_unclustered_articles_sb_none(self, mock_logger_arg):
        mock_logger_arg.reset_mock() # Good practice, though a fresh mock is passed each time
        with patch('core.clustering.db_access.sb', None):
            result = fetch_unclustered_articles()
            self.assertEqual(result, [])
            mock_logger_arg.warning.assert_called_once_with("Supabase client is not initialized. Cannot perform fetch_unclustered_articles operation.")


class TestFetchData(unittest.TestCase):
    @patch('core.clustering.db_access.sb')
    def test_fetch_data_success(self, mock_sb):
        # Setup mock
        mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(
            data=[{"id": 1, "title": "Test Article"}], error=None)

        from core.clustering.db_access import fetch_data  # Import here to avoid circular import
        result = fetch_data("some_table")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], 1)

    @patch('core.clustering.db_access.logger')
    def test_fetch_data_api_error(self, mock_logger_arg):
        mock_logger_arg.reset_mock()
        error_dict = {"message": "API error"}
        with patch('core.clustering.db_access.sb.table.return_value.select.return_value.execute',
                   side_effect=APIError(error_dict)):
            from core.clustering.db_access import fetch_data  # Import here to avoid circular import
            result = fetch_data("some_table")
            self.assertEqual(result, [])
            mock_logger_arg.error.assert_called_once_with(f"Supabase APIError in fetch_data: {error_dict}")

    @patch('core.clustering.db_access.logger')
    def test_fetch_data_generic_error(self, mock_logger_arg):
        mock_logger_arg.reset_mock()
        with patch('core.clustering.db_access.sb.table.return_value.select.return_value.execute',
                   side_effect=Exception("Generic error")):
            from core.clustering.db_access import fetch_data  # Import here to avoid circular import
            result = fetch_data("some_table")
            self.assertEqual(result, [])
            mock_logger_arg.error.assert_called_once_with("Unexpected error in fetch_data: Generic error")

    @patch('core.clustering.db_access.logger')
    def test_fetch_data_sb_none(self, mock_logger_arg):
        mock_logger_arg.reset_mock()
        with patch('core.clustering.db_access.sb', None):
            from core.clustering.db_access import fetch_data  # Import here to avoid circular import
            result = fetch_data("some_table")
            self.assertEqual(result, [])
            mock_logger_arg.warning.assert_called_once_with("Supabase client is not initialized. Cannot perform fetch_data operation.")
