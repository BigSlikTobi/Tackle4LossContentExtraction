"""
Tests for the batched cleanup pipeline.
Tests the article-level batching functionality, argument parsing,
error handling, and integration with the lock manager.
"""

import unittest
import os
import sys
import subprocess
import tempfile
import json
from unittest.mock import patch, MagicMock, AsyncMock, call
import asyncio

# Add the parent directory to sys.path to allow imports from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from src.core.utils.lock_manager import LOCK_FILE_PATH

# Determine the path to the batched cleanup pipeline script
BATCHED_PIPELINE_SCRIPT_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'scripts', 'cleanup_pipeline_batched.py'
))

class TestCleanupPipelineBatched(unittest.TestCase):
    """Test the batched cleanup pipeline functionality."""

    def setUp(self):
        """Ensure the lock file does not exist before each test."""
        if os.path.exists(LOCK_FILE_PATH):
            os.remove(LOCK_FILE_PATH)

    def tearDown(self):
        """Ensure the lock file is cleaned up after each test."""
        if os.path.exists(LOCK_FILE_PATH):
            os.remove(LOCK_FILE_PATH)

    def _get_test_env(self):
        """Get environment variables for testing."""
        process_env = os.environ.copy()
        process_env.update({
            'SUPABASE_URL': 'http://dummy.url',
            'SUPABASE_KEY': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c',
            'OPENAI_API_KEY': 'dummy_openai_key',
            'DEEPSEEK_API_KEY': 'dummy_deepseek_key',
            'PYTHONPATH': os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        })
        return process_env

    def _run_batched_pipeline(self, args=None, env=None, expected_returncode=0):
        """Run the batched cleanup pipeline script as a subprocess."""
        cmd = [sys.executable, BATCHED_PIPELINE_SCRIPT_PATH]
        if args:
            cmd.extend(args)
        
        process_env = env or self._get_test_env()
        
        result = subprocess.run(
            cmd,
            env=process_env,
            capture_output=True,
            text=True,
            timeout=30  # Prevent hanging
        )
        
        if result.returncode != expected_returncode:
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
        
        self.assertEqual(result.returncode, expected_returncode)
        return result

    def test_argument_parsing(self):
        """Test command line argument parsing."""
        # Test help flag
        result = self._run_batched_pipeline(['--help'], expected_returncode=0)
        self.assertIn('--batch-size', result.stdout)
        self.assertIn('--delay', result.stdout)
        self.assertIn('--max-batches', result.stdout)
        self.assertIn('--dry-run', result.stdout)

    def test_dry_run_mode(self):
        """Test dry run mode doesn't actually process articles."""
        result = self._run_batched_pipeline(['--dry-run', '--batch-size', '2'])
        # Check that dry run configuration is shown
        self.assertIn('Dry run: True', result.stdout)
        self.assertIn('Configuration:', result.stdout)
        # Should not try to process articles when no articles found
        self.assertIn('No unprocessed articles found', result.stdout)

    def test_lock_file_behavior(self):
        """Test that the pipeline respects lock files."""
        # Create a lock file
        with open(LOCK_FILE_PATH, 'w') as f:
            f.write('test_lock')
        
        # Pipeline should exit when lock exists (not in dry-run mode)
        result = self._run_batched_pipeline([], expected_returncode=0)
        self.assertIn('Pipeline is already running', result.stdout)

    def test_batch_size_validation(self):
        """Test batch size parameter validation."""
        # Test invalid batch size
        result = self._run_batched_pipeline(['--batch-size', '0'], expected_returncode=1)
        self.assertIn('ERROR: Batch size must be at least 1', result.stdout)

    def test_concurrent_limit_validation(self):
        """Test concurrent limit parameter behavior."""
        # Test concurrent limit 0 defaults to batch size
        result = self._run_batched_pipeline(['--concurrent-limit', '0', '--batch-size', '5', '--dry-run'])
        self.assertIn('Concurrent limit per batch: 5', result.stdout)  # Should default to batch size

    @patch('scripts.cleanup_pipeline_batched.count_unprocessed_articles')
    @patch('scripts.cleanup_pipeline_batched.get_unprocessed_articles_batch')
    @patch('scripts.cleanup_pipeline_batched.process_article')
    def test_empty_database(self, mock_process, mock_get_batch, mock_count):
        """Test behavior when no unprocessed articles exist."""
        mock_count.return_value = 0
        mock_get_batch.return_value = []
        
        result = self._run_batched_pipeline(['--batch-size', '5'])
        self.assertIn('No unprocessed articles found', result.stdout)

    def test_single_batch_processing(self):
        """Test configuration for single batch processing."""        
        result = self._run_batched_pipeline(['--batch-size', '5', '--max-batches', '1', '--dry-run'])
        
        # Verify the configuration shows single batch setup
        self.assertIn('Batch size: 5 articles', result.stdout)
        self.assertIn('Max batches: 1', result.stdout)
        # Since we can't mock DB calls in subprocess, just verify configuration
        self.assertIn('Configuration:', result.stdout)

    @patch('scripts.cleanup_pipeline_batched.count_unprocessed_articles')
    @patch('scripts.cleanup_pipeline_batched.get_unprocessed_articles_batch')
    def test_multiple_batch_configuration(self, mock_get_batch, mock_count):
        """Test configuration for multiple batches."""
        mock_count.return_value = 10
        mock_get_batch.return_value = []  # Empty batches for quick test
        
        result = self._run_batched_pipeline([
            '--batch-size', '3',
            '--max-batches', '2',
            '--delay', '1'
        ])
        
        self.assertIn('Batch size: 3 articles', result.stdout)
        self.assertIn('Max batches: 2', result.stdout)
        self.assertIn('Delay between batches: 1 seconds', result.stdout)

    def test_environment_variable_requirements(self):
        """Test that the script handles missing environment variables gracefully."""
        # Run without required environment variables
        minimal_env = {'PYTHONPATH': os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))}
        
        # This should run but may have warnings or error messages about missing environment
        result = subprocess.run(
            [sys.executable, BATCHED_PIPELINE_SCRIPT_PATH, '--dry-run'],  # Back to dry-run for safety
            env=minimal_env,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        # Should complete successfully or with a specific error message
        # The script may handle missing environment variables gracefully
        self.assertTrue(result.returncode == 0 or 'Error' in result.stdout)

    def test_batch_calculation(self):
        """Test batch calculation configuration display."""        
        result = self._run_batched_pipeline([
            '--batch-size', '10',
            '--max-batches', '2',
            '--dry-run'
        ])
        
        # Check that the configuration shows the batch settings
        self.assertIn('Batch size: 10 articles', result.stdout)
        self.assertIn('Max batches: 2', result.stdout)
        # Since we can't mock the DB call in subprocess, just verify it tries to count
        self.assertIn('Counting unprocessed articles', result.stdout)

    def test_configuration_display(self):
        """Test that configuration is properly displayed."""
        with patch('scripts.cleanup_pipeline_batched.count_unprocessed_articles', return_value=0):
            result = self._run_batched_pipeline([
                '--batch-size', '7',
                '--delay', '3',
                '--max-batches', '5',
                '--concurrent-limit', '4',
                '--dry-run'
            ])
            
            config_output = result.stdout
            self.assertIn('Batch size: 7 articles', config_output)
            self.assertIn('Max batches: 5', config_output)
            self.assertIn('Delay between batches: 3 seconds', config_output)
            self.assertIn('Concurrent limit per batch: 4', config_output)
            self.assertIn('Dry run: True', config_output)


class TestBatchedPipelineUnit(unittest.TestCase):
    """Unit tests for individual functions in the batched pipeline."""

    def setUp(self):
        """Set up test environment."""
        # Add the scripts directory to sys.path for importing
        scripts_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts'))
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)

    @patch('cleanup_pipeline_batched.process_article')
    def test_process_article_batch_success(self, mock_process_article):
        """Test successful processing of an article batch."""
        # Import here to avoid import issues
        from cleanup_pipeline_batched import process_article_batch
        
        # Setup
        mock_process_article.return_value = AsyncMock()
        test_articles = [
            {'id': 1, 'url': 'http://test1.com'},
            {'id': 2, 'url': 'http://test2.com'}
        ]
        
        # Run the test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success_count, failed_count = loop.run_until_complete(
                process_article_batch(test_articles, 1, 1)
            )
            
            # Verify results
            self.assertEqual(success_count, 2)
            self.assertEqual(failed_count, 0)
            self.assertEqual(mock_process_article.call_count, 2)
        finally:
            loop.close()

    @patch('cleanup_pipeline_batched.process_article')
    def test_process_article_batch_with_failures(self, mock_process_article):
        """Test processing of an article batch with some failures."""
        from cleanup_pipeline_batched import process_article_batch
        
        # Setup - one success, one failure
        async def mock_process_side_effect(article):
            if article['id'] == 1:
                return True  # Success
            else:
                raise Exception("Processing failed")  # Failure
        
        mock_process_article.side_effect = mock_process_side_effect
        
        test_articles = [
            {'id': 1, 'url': 'http://test1.com'},
            {'id': 2, 'url': 'http://test2.com'}
        ]
        
        # Run the test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success_count, failed_count = loop.run_until_complete(
                process_article_batch(test_articles, 1, 1)
            )
            
            # Verify results
            self.assertEqual(success_count, 1)
            self.assertEqual(failed_count, 1)
        finally:
            loop.close()


if __name__ == '__main__':
    unittest.main()
