import unittest
from unittest.mock import patch, MagicMock
import logging
import os
import sys

# Define patchers
patch_os_environ = patch.dict(os.environ, {"SUPABASE_URL": "http://dummy.example.com", "SUPABASE_KEY": "dummy_key"}, clear=True)
patch_sys_exit = patch('sys.exit')
patch_create_client = patch('supabase.create_client')

active_patches_list = [patch_os_environ, patch_sys_exit, patch_create_client]

mock_supabase_instance_globally = MagicMock()

# Global variables to hold imported names after patching
update_article_in_db = None
# update_article_logger global variable is not strictly needed for patching if we patch by string path.
# We keep it for consistency if tests need to refer to the logger object itself, though not for patching its methods.
update_article_logger = None

def setUpModule():
    """Set up patches and import modules AFTER patches are active."""
    global update_article_in_db, update_article_logger

    for p_obj in active_patches_list:
        started_patch = p_obj.start()
        if p_obj == patch_create_client:
            started_patch.return_value = mock_supabase_instance_globally

    from core.db.update_article import update_article_in_db as uaidb, logger as ual
    update_article_in_db = uaidb
    update_article_logger = ual # The actual logger object from core.db.update_article

def tearDownModule():
    """Stop all patches."""
    for p_obj in active_patches_list:
        try:
            p_obj.stop()
        except RuntimeError as e:
            print(f"Error stopping patch {p_obj}: {e}")


class TestUpdateArticle(unittest.TestCase):

    @patch('core.db.update_article.supabase_client')
    def test_update_article_success(self, mock_supabase_client_for_test):
        mock_response = MagicMock()
        mock_response.error = None
        mock_response.data = [{'id': 1, 'title': 'Updated Article'}]

        mock_execute = mock_supabase_client_for_test.table.return_value.update.return_value.eq.return_value.execute
        mock_execute.return_value = mock_response

        article_id = 1
        update_data = {"status": "processed"}
        result = update_article_in_db(article_id, update_data)

        self.assertTrue(result)
        mock_supabase_client_for_test.table.assert_called_once_with("SourceArticles")
        # ... (rest of assertions)
        mock_supabase_client_for_test.table.return_value.update.assert_called_once_with(update_data)
        mock_supabase_client_for_test.table.return_value.update.return_value.eq.assert_called_once_with("id", article_id)
        mock_execute.assert_called_once_with()

    # Patch the 'error' method of the logger instance named 'logger' within the 'core.db.update_article' module.
    @patch('core.db.update_article.logger.error')
    @patch('core.db.update_article.supabase_client')
    def test_update_article_failure_db_error(self, mock_supabase_client_for_test, mock_logger_error_method):
        # Order of mock arguments is based on decorator order (from bottom up)
        mock_response = MagicMock()
        mock_response.error = {"message": "Database connection failed", "code": "500"}
        mock_response.data = []

        mock_execute = mock_supabase_client_for_test.table.return_value.update.return_value.eq.return_value.execute
        mock_execute.return_value = mock_response

        article_id = 2
        update_data = {"status": "failed"}
        result = update_article_in_db(article_id, update_data)

        self.assertFalse(result)
        mock_supabase_client_for_test.table.assert_called_once_with("SourceArticles")
        mock_logger_error_method.assert_called_once()
        args, _ = mock_logger_error_method.call_args
        self.assertIn(f"Failed to update database for article {article_id}", args[0])
        self.assertIn("Database connection failed", args[0])

    @patch('core.db.update_article.logger.error')
    @patch('core.db.update_article.supabase_client')
    def test_update_article_failure_exception(self, mock_supabase_client_for_test, mock_logger_error_method):
        # Order of mock arguments is based on decorator order (from bottom up)
        mock_execute = mock_supabase_client_for_test.table.return_value.update.return_value.eq.return_value.execute
        mock_execute.side_effect = Exception("Network timeout")

        article_id = 3
        update_data = {"status": "error"}
        result = update_article_in_db(article_id, update_data)

        self.assertFalse(result)
        mock_logger_error_method.assert_called_once()
        args, _ = mock_logger_error_method.call_args
        self.assertIn(f"Failed to update database for article {article_id}", args[0])
        self.assertIn("Network timeout", args[0]) # Check args[0] for the content

if __name__ == '__main__':
    unittest.main()
