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

    @patch('core.clustering.db_access.logger', mock_logger)
    @patch('core.clustering.db_access.sb')
    def test_fetch_existing_clusters_success(self, mock_sb):
        mock_logger.reset_mock()
        mock_data = [
            {"cluster_id": "c1", "centroid": "[0.1,0.2]", "member_count": 5},
            {"cluster_id": "c2", "centroid": [0.3,0.4], "member_count": 3}, # Test list format for centroid too
        ]
        mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=mock_data, error=None)

        clusters = fetch_existing_clusters()
        self.assertEqual(len(clusters), 2)
        self.assertEqual(clusters[0][0], "c1")
        np.testing.assert_array_almost_equal(clusters[0][1], np.array([0.1, 0.2]))
        self.assertEqual(clusters[0][2], 5)
        mock_logger.error.assert_not_called()

    @patch('core.clustering.db_access.logger', mock_logger)
    @patch('core.clustering.db_access.sb')
    def test_fetch_existing_clusters_api_error(self, mock_sb):
        mock_logger.reset_mock()
        error_dict = {"message": "Fetch failed"}
        mock_sb.table.return_value.select.return_value.execute.side_effect = APIError(error_dict)

        clusters = fetch_existing_clusters()
        self.assertEqual(clusters, [])
        mock_logger.error.assert_called_once_with(f"Supabase APIError in fetch_existing_clusters: {error_dict}")

    @patch('core.clustering.db_access.logger', mock_logger)
    @patch('core.clustering.db_access.sb')
    def test_update_cluster_in_db_success(self, mock_sb):
        mock_logger.reset_mock()
        mock_execute = mock_sb.table.return_value.update.return_value.eq.return_value.execute
        mock_execute.return_value = MagicMock(error=None) # Simulate successful execution

        update_cluster_in_db("c1", np.array([0.1]*768), 10, True) # Use 768-dim array
        mock_execute.assert_called_once()
        mock_logger.error.assert_not_called()
        # Check if logger.debug was called with the correct message
        # This requires logger to be unmocked or more sophisticated mocking if we want to check specific debug messages
        # For now, just checking no error logs.

    @patch('core.clustering.db_access.logger', mock_logger)
    @patch('core.clustering.db_access.sb')
    def test_update_cluster_in_db_api_error(self, mock_sb):
        mock_logger.reset_mock()
        error_dict = {"message": "Update failed"}
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.side_effect = APIError(error_dict)

        update_cluster_in_db("c1", np.array([0.1]*768), 10)
        mock_logger.error.assert_called_once_with(f"Supabase APIError updating cluster c1: {error_dict}")

    @patch('core.clustering.db_access.logger', mock_logger)
    @patch('core.clustering.db_access.sb')
    @patch('core.clustering.db_access.uuid.uuid4') # Mock uuid.uuid4 directly
    def test_create_cluster_in_db_success(self, mock_uuid4, mock_sb): # Renamed mock_uuid to mock_uuid4
        mock_logger.reset_mock()
        # Configure mock_uuid4 to return a specific UUID object, then str() will be called on it
        # The actual UUID value doesn't matter as much as it being consistent.
        test_uuid_str = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
        mock_uuid_obj = MagicMock()
        mock_uuid_obj.__str__.return_value = test_uuid_str
        mock_uuid4.return_value = mock_uuid_obj

        mock_execute = mock_sb.table.return_value.insert.return_value.execute
        mock_execute.return_value = MagicMock(error=None)

        cluster_id = create_cluster_in_db(np.array([0.2]*768), 1)
        self.assertEqual(cluster_id, test_uuid_str) # Should return the generated UUID string
        mock_execute.assert_called_once()
        # Verify the data passed to insert contains the mocked cluster_id
        called_with_data = mock_sb.table.return_value.insert.call_args[0][0]
        self.assertEqual(called_with_data['cluster_id'], test_uuid_str)
        mock_logger.error.assert_not_called()

    @patch('core.clustering.db_access.logger', mock_logger)
    @patch('core.clustering.db_access.sb')
    def test_create_cluster_in_db_api_error(self, mock_sb):
        mock_logger.reset_mock()
        error_dict = {"message": "Insert failed"}
        mock_sb.table.return_value.insert.return_value.execute.side_effect = APIError(error_dict)

        cluster_id = create_cluster_in_db(np.array([0.2]*768), 1)
        self.assertIsNone(cluster_id)
        mock_logger.error.assert_called_once_with(f"Supabase APIError creating cluster: {error_dict}")

    @patch('core.clustering.db_access.logger', mock_logger)
    @patch('core.clustering.db_access.sb')
    def test_assign_article_to_cluster_success(self, mock_sb):
        mock_logger.reset_mock()
        mock_execute = mock_sb.table.return_value.update.return_value.eq.return_value.execute
        mock_execute.return_value = MagicMock(error=None)

        assign_article_to_cluster(1, "c1")
        mock_execute.assert_called_once()
        mock_logger.error.assert_not_called()

    @patch('core.clustering.db_access.logger', mock_logger)
    @patch('core.clustering.db_access.sb')
    def test_assign_article_to_cluster_api_error(self, mock_sb):
        mock_logger.reset_mock()
        error_dict = {"message": "Assign failed"}
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.side_effect = APIError(error_dict)

        assign_article_to_cluster(1, "c1")
        mock_logger.error.assert_called_once_with(f"Supabase APIError assigning article 1 to cluster c1: {error_dict}")

    @patch('core.clustering.db_access.logger', mock_logger)
    @patch('core.clustering.db_access.sb')
    def test_batch_assign_articles_to_cluster_success(self, mock_sb):
        mock_logger.reset_mock()
        mock_execute = mock_sb.table.return_value.upsert.return_value.execute
        mock_execute.return_value = MagicMock(error=None)

        batch_assign_articles_to_cluster([(1, "c1"), (2, "c2")])
        mock_execute.assert_called_once()
        mock_logger.error.assert_not_called()

    @patch('core.clustering.db_access.logger', mock_logger)
    @patch('core.clustering.db_access.sb')
    def test_batch_assign_articles_to_cluster_api_error(self, mock_sb):
        mock_logger.reset_mock()
        error_dict = {"message": "Batch assign failed"}
        mock_sb.table.return_value.upsert.return_value.execute.side_effect = APIError(error_dict)

        batch_assign_articles_to_cluster([(1, "c1"), (2, "c2")])
        mock_logger.error.assert_called_once_with(f"Supabase APIError batch assigning articles: {error_dict}")

    @patch('core.clustering.db_access.logger', mock_logger)
    @patch('core.clustering.db_access.sb')
    def test_repair_zero_centroid_clusters_success_no_fix_needed(self, mock_sb):
        mock_logger.reset_mock()
        # Mock initial fetch of clusters
        mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(
            data=[{"cluster_id": "c1", "centroid": "[0.1,0.2,0.3]"}] # Non-zero centroid
        )
        fixed = repair_zero_centroid_clusters()
        self.assertEqual(fixed, [])
        mock_logger.info.assert_any_call("No zero centroid clusters found") # Check specific log
        mock_logger.error.assert_not_called()

    @patch('core.clustering.db_access.logger', mock_logger)
    @patch('core.clustering.db_access.sb')
    def test_repair_zero_centroid_clusters_success_fix_applied(self, mock_sb):
        mock_logger.reset_mock()

        mock_clusters_table = MagicMock()
        mock_source_articles_table = MagicMock()

        def table_side_effect(table_name):
            if table_name == "clusters":
                return mock_clusters_table
            elif table_name == "SourceArticles":
                return mock_source_articles_table
            return MagicMock()
        mock_sb.table.side_effect = table_side_effect

        # Mock initial fetch of clusters - one zero centroid
        mock_clusters_response_data = [
            {"cluster_id": "c1", "centroid": "[0,0,0]"},
            {"cluster_id": "c2", "centroid": "[1,1,1]"} # Valid one
        ]
        mock_clusters_table.select.return_value.execute.return_value = MagicMock(data=mock_clusters_response_data, error=None)

        # Mock fetching articles for cluster c1 (using 768-dim embeddings)
        embedding_c1_art1 = np.array([0.1]*768).tolist()
        embedding_c1_art2 = np.array([0.4]*768).tolist()
        mock_articles_c1_response_data = [
            {"id": 1, "ArticleVector": [{"embedding": str(embedding_c1_art1)}]},
            {"id": 2, "ArticleVector": [{"embedding": str(embedding_c1_art2)}]}
        ]
        mock_source_articles_table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=mock_articles_c1_response_data, error=None)

        # Mock the update call within update_cluster_in_db for c1 (which is on "clusters" table)
        mock_clusters_table.update.return_value.eq.return_value.execute.return_value = MagicMock(error=None)

        fixed = repair_zero_centroid_clusters()
        self.assertEqual(fixed, ["c1"])
        mock_logger.info.assert_any_call("Recalculated centroid for cluster c1")
        mock_logger.info.assert_any_call("Fixed centroids for 1 clusters")
        mock_logger.error.assert_not_called()


    @patch('core.clustering.db_access.logger', mock_logger)
    @patch('core.clustering.db_access.sb')
    def test_repair_zero_centroid_clusters_fetch_clusters_api_error(self, mock_sb):
        mock_logger.reset_mock()
        error_dict = {"message": "Fetch clusters failed"}
        mock_sb.table.return_value.select.return_value.execute.side_effect = APIError(error_dict)

        fixed = repair_zero_centroid_clusters()
        self.assertEqual(fixed, [])
        mock_logger.error.assert_called_once_with(f"Supabase APIError fetching clusters in repair_zero_centroid_clusters: {error_dict}")

    # TODO: Add more tests for recalculate_cluster_member_counts and update_old_clusters_status

    @patch('core.clustering.db_access.logger', mock_logger)
    @patch('core.clustering.db_access.sb')
    def test_recalculate_cluster_member_counts_success_no_discrepancies(self, mock_sb):
        mock_logger.reset_mock()

        mock_clusters_table = MagicMock()
        mock_source_articles_table = MagicMock()

        def table_side_effect(table_name):
            if table_name == "clusters":
                return mock_clusters_table
            elif table_name == "SourceArticles":
                return mock_source_articles_table
            return MagicMock()
        mock_sb.table.side_effect = table_side_effect

        mock_clusters_data = [{"cluster_id": "c1", "member_count": 10}]
        mock_articles_data = [{"id": i, "cluster_id": "c1"} for i in range(10)]

        mock_clusters_table.select("cluster_id", "member_count").execute.return_value = MagicMock(data=mock_clusters_data, error=None)

        # Explicit chain for mock_source_articles_table
        mock_sa_select = mock_source_articles_table.select("id", "cluster_id")
        mock_sa_not = mock_sa_select.not_
        mock_sa_is = mock_sa_not.is_("cluster_id", None)
        mock_sa_is.execute.return_value = MagicMock(data=mock_articles_data, error=None)

        discrepancies = recalculate_cluster_member_counts()
        self.assertEqual(discrepancies, {})
        mock_logger.info.assert_any_call("All cluster member counts are accurate")
        mock_logger.error.assert_not_called()

    @patch('core.clustering.db_access.logger', mock_logger)
    @patch('core.clustering.db_access.sb')
    def test_recalculate_cluster_member_counts_api_error_fetching_clusters(self, mock_sb):
        mock_logger.reset_mock()
        error_dict = {"message": "DB error"}
        # This mock will apply to the first execute call, which is fetching clusters
        mock_sb.table.return_value.select.return_value.execute.side_effect = APIError(error_dict)

        discrepancies = recalculate_cluster_member_counts()
        self.assertEqual(discrepancies, {})
        mock_logger.error.assert_called_with(f"Supabase APIError fetching data in recalculate_cluster_member_counts: {error_dict}")

    @patch('core.clustering.db_access.logger', mock_logger)
    @patch('core.clustering.db_access.sb')
    def test_update_old_clusters_status_success_no_updates(self, mock_sb):
        mock_logger.reset_mock()
        # updated_at is recent enough
        recent_time = (datetime.now() - timedelta(days=1)).isoformat()
        mock_clusters_data = [{"cluster_id": "c1", "updated_at": recent_time, "status": "UPDATED"}]

        mock_sb.table.return_value.select.return_value.not_.return_value.eq.return_value.execute.return_value = MagicMock(data=mock_clusters_data, error=None)

        num_updated = update_old_clusters_status()
        self.assertEqual(num_updated, 0)
        mock_logger.debug.assert_any_call("No clusters needed to be updated to 'OLD' status")
        mock_logger.error.assert_not_called()

    @patch('core.clustering.db_access.logger', mock_logger)
    @patch('core.clustering.db_access.sb')
    def test_update_old_clusters_status_api_error_fetching(self, mock_sb):
        mock_logger.reset_mock()

        mock_clusters_table = MagicMock()
        def table_side_effect(table_name):
            if table_name == "clusters":
                return mock_clusters_table
            return MagicMock()
        mock_sb.table.side_effect = table_side_effect

        error_dict = {"message": "Fetch error"}
        # Explicit chain for mock_clusters_table
        mock_cl_select = mock_clusters_table.select("cluster_id", "updated_at")
        mock_cl_not = mock_cl_select.not_
        mock_cl_eq = mock_cl_not.eq("status", "OLD")
        mock_cl_eq.execute.side_effect = APIError(error_dict)

        num_updated = update_old_clusters_status()
        self.assertEqual(num_updated, 0)
        mock_logger.error.assert_called_once_with(f"Supabase APIError fetching clusters in update_old_clusters_status: {error_dict}")


if __name__ == '__main__':
    unittest.main()
