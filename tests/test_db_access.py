import unittest
from unittest.mock import patch, MagicMock
import logging
from types import SimpleNamespace

# Assuming core.clustering.db_access is the module path
# Adjust if db_access is imported differently or sb is initialized elsewhere globally
# For testing, we might need to patch 'src.core.clustering.db_access.sb'

# We need to ensure that 'sb' can be patched BEFORE it's used by the module.
# One way is to ensure the module is loaded AFTER patches, or patch 'sb' where it's defined.
# For simplicity here, we'll assume 'from src.core.clustering.db_access import recalculate_cluster_member_counts'
# works and we can patch 'src.core.clustering.db_access.sb'.

# To make patching sb reliable, especially if it's initialized at import time of db_access,
# it's often better to ensure db_access is imported *after* the patch is set up,
# or to have sb dependency-injected. Given current structure, we patch by its module path.

# Import the module and function to be tested
from src.core.clustering import db_access # Import the module itself
from src.core.clustering.db_access import recalculate_cluster_member_counts, RPCCallFailedError


# Disable logging for tests unless specifically testing log output
# logging.disable(logging.CRITICAL) # Disables logging globally for tests - REMOVE THIS

class TestRecalculateClusterMemberCounts(unittest.TestCase):

    def setUp(self):
        # This mock will be used to replace 'sb' in the db_access module for each test
        self.patcher = patch.object(db_access, 'sb') # Patch sb on the imported db_access module
        self.mock_sb = self.patcher.start()
        self.addCleanup(self.patcher.stop) # Ensure patch is stopped after test

        # self.mock_rpc_call is the object returned by sb.rpc()
        # It needs to have an 'execute' method.
        self.mock_rpc_call = MagicMock()
        self.mock_sb.rpc.return_value = self.mock_rpc_call


    def test_recalculate_successful_rpc_call_with_discrepancies(self):
        # Expected JSON response from the SQL function
        rpc_response_data = {
            "message": "Successfully recalculated cluster counts via RPC.",
            "updated_clusters": ["uuid1", "uuid2"],
            "deleted_clusters": ["uuid3"],
            "unassigned_articles_from_single_member_clusters": [101, 102],
            "discrepancies": {
                "cluster_A": {"old": 10, "new": 12},
                "cluster_B": {"old": 5, "new": 0}
            }
        }
        mock_response_obj = SimpleNamespace(data=rpc_response_data)
        self.mock_rpc_call.execute.return_value = mock_response_obj

        expected_discrepancies = {
            "cluster_A": (10, 12),
            "cluster_B": (5, 0)
        }

        with patch.object(logging.getLogger('src.core.clustering.db_access'), 'info') as mock_logger_info:
            result = recalculate_cluster_member_counts()

        self.mock_sb.rpc.assert_called_once_with('recalculate_all_cluster_member_counts')
        self.mock_rpc_call.execute.assert_called_once()
        self.assertEqual(result, expected_discrepancies)

        mock_logger_info.assert_any_call("Calling RPC 'recalculate_all_cluster_member_counts' to fix cluster member counts...")
        mock_logger_info.assert_any_call("Successfully recalculated cluster counts via RPC.")
        mock_logger_info.assert_any_call(f"Clusters updated: {len(rpc_response_data['updated_clusters'])}")
        mock_logger_info.assert_any_call(f"Clusters deleted: {len(rpc_response_data['deleted_clusters'])}")
        mock_logger_info.assert_any_call(f"Articles unassigned from single-member clusters: {len(rpc_response_data['unassigned_articles_from_single_member_clusters'])}")
        mock_logger_info.assert_any_call(f"Found {len(expected_discrepancies)} cluster member count discrepancies through RPC.")


    def test_recalculate_successful_rpc_call_no_discrepancies(self):
        rpc_response_data = {
            "message": "Successfully recalculated cluster counts via RPC.",
            "updated_clusters": [],
            "deleted_clusters": [],
            "unassigned_articles_from_single_member_clusters": [],
            "discrepancies": {}
        }
        mock_response_obj = SimpleNamespace(data=rpc_response_data)
        self.mock_rpc_call.execute.return_value = mock_response_obj

        expected_discrepancies = {}

        with patch.object(logging.getLogger('src.core.clustering.db_access'), 'info') as mock_logger_info:
            result = recalculate_cluster_member_counts()

        self.mock_sb.rpc.assert_called_once_with('recalculate_all_cluster_member_counts')
        self.mock_rpc_call.execute.assert_called_once()
        self.assertEqual(result, expected_discrepancies)
        mock_logger_info.assert_any_call("No cluster member count discrepancies reported by RPC.")

    def test_recalculate_rpc_call_returns_no_data(self):
        mock_response_obj = SimpleNamespace(data=None) # Simulate no data in response
        self.mock_rpc_call.execute.return_value = mock_response_obj

        with patch.object(logging.getLogger('src.core.clustering.db_access'), 'error') as mock_logger_error:
            result = recalculate_cluster_member_counts()

        self.assertEqual(result, {})
        mock_logger_error.assert_any_call("No data returned from 'recalculate_all_cluster_member_counts' RPC call or response.data is empty, and no exception was raised during the call.")

    def test_recalculate_rpc_call_raises_exception(self):
        # Make rpc().execute() raise an exception
        # For this test, self.mock_rpc_call.execute itself raises the error.
        self.mock_rpc_call.execute.side_effect = RPCCallFailedError("RPC Error")

        with patch.object(logging.getLogger('src.core.clustering.db_access'), 'error') as mock_logger_error:
            result = recalculate_cluster_member_counts()

        self.assertEqual(result, {})
        mock_logger_error.assert_any_call("Error calling 'recalculate_all_cluster_member_counts' RPC: RPC Error", exc_info=True)

    def test_recalculate_sb_not_initialized(self):
        # For this test, we want 'sb' to be None.
        # Stop the default patcher for 'sb' and set it to None directly.
        self.patcher.stop()
        with patch.object(db_access, 'sb', None): # Patch sb on the imported module to be None
            with self.assertRaisesRegex(RuntimeError, "Supabase client not initialized."):
                recalculate_cluster_member_counts()
        self.patcher.start() # Restart for other tests if any in this class

    def test_recalculate_malformed_discrepancies_in_rpc_response(self):
        rpc_response_data = {
            "message": "OK",
            "discrepancies": {
                "cluster_A": {"old_typo": 10, "new_typo": 12},
                "cluster_B": "not_a_dict"
            }
        }
        mock_response_obj = SimpleNamespace(data=rpc_response_data)
        self.mock_rpc_call.execute.return_value = mock_response_obj

        expected_discrepancies = {}

        with patch.object(logging.getLogger('src.core.clustering.db_access'), 'warning') as mock_logger_warning:
            result = recalculate_cluster_member_counts()

        self.assertEqual(result, expected_discrepancies)
        mock_logger_warning.assert_any_call("Unexpected format for discrepancy item: cluster_A -> {'old_typo': 10, 'new_typo': 12}")
        mock_logger_warning.assert_any_call("Unexpected format for discrepancy item: cluster_B -> not_a_dict")

if __name__ == '__main__':
            # Need to make sure imports from src.core.clustering.db_access are available
    # This might require adjusting sys.path if 'tests' is run as the top-level script
    # For example, by adding the project root to sys.path:
    # import sys
    # import os
    # sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    unittest.main()
