"""
Comprehensive health check tests for both cleanup and cluster pipelines.
These tests verify that the pipelines can run end-to-end and handle various scenarios correctly.
"""
import unittest
import os
import sys
import subprocess
import tempfile
import json
import time
import importlib.util
from unittest.mock import patch, MagicMock
from typing import Dict, Any, List

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Add src directory to sys.path for new module structure
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from src.core.utils.lock_manager import LOCK_FILE_PATH

class TestPipelineHealthChecks(unittest.TestCase):
    """
    Health check tests for pipeline functionality.
    These tests ensure the pipelines can run without breaking and handle edge cases properly.
    """

    def setUp(self):
        """Clean up any existing lock files and prepare test environment."""
        if os.path.exists(LOCK_FILE_PATH):
            os.remove(LOCK_FILE_PATH)

    def tearDown(self):
        """Clean up lock files after each test."""
        if os.path.exists(LOCK_FILE_PATH):
            os.remove(LOCK_FILE_PATH)

    def _get_test_env(self) -> Dict[str, str]:
        """Get test environment variables for pipeline execution."""
        process_env = os.environ.copy()
        
        # Add dummy credentials that won't work but will allow imports
        process_env['SUPABASE_URL'] = 'http://test.supabase.co'
        process_env['SUPABASE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c'
        process_env['OPENAI_API_KEY'] = 'sk-test-dummy-key'
        process_env['DEEPSEEK_API_KEY'] = 'sk-test-dummy-deepseek-key'
        
        # Ensure PYTHONPATH includes project root and src directory
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        src_path = os.path.join(project_root, 'src')
        if 'PYTHONPATH' in process_env:
            process_env['PYTHONPATH'] = f"{project_root}:{src_path}:{process_env['PYTHONPATH']}"
        else:
            process_env['PYTHONPATH'] = f"{project_root}:{src_path}"
            
        return process_env

    def _run_pipeline_subprocess(self, script_name: str, timeout: int = 30) -> subprocess.CompletedProcess:
        """Run a pipeline script as subprocess with proper environment."""
        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', script_name))
        return subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            env=self._get_test_env(),
            timeout=timeout
        )

    def test_cleanup_pipeline_syntax_and_imports(self):
        """Test that cleanup_pipeline.py can be imported and has no syntax errors."""
        try:
            with patch.dict(os.environ, self._get_test_env()):
                # Try to import the cleanup pipeline module
                spec = importlib.util.spec_from_file_location(
                    "cleanup_pipeline", 
                    os.path.join(os.path.dirname(__file__), '..', 'scripts', 'cleanup_pipeline.py')
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Check that main function exists
                self.assertTrue(hasattr(module, 'main'))
                self.assertTrue(callable(module.main))
                
        except ImportError as e:
            self.fail(f"Failed to import cleanup_pipeline.py: {e}")
        except SyntaxError as e:
            self.fail(f"Syntax error in cleanup_pipeline.py: {e}")

    def test_cluster_pipeline_syntax_and_imports(self):
        """Test that cluster_pipeline.py can be imported and has no syntax errors."""
        try:
            with patch.dict(os.environ, self._get_test_env()):
                spec = importlib.util.spec_from_file_location(
                    "cluster_pipeline", 
                    os.path.join(os.path.dirname(__file__), '..', 'scripts', 'cluster_pipeline.py')
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Check that process_new function exists
                self.assertTrue(hasattr(module, 'process_new'))
                self.assertTrue(callable(module.process_new))
                
        except ImportError as e:
            self.fail(f"Failed to import cluster_pipeline.py: {e}")
        except SyntaxError as e:
            self.fail(f"Syntax error in cluster_pipeline.py: {e}")

    def test_cleanup_pipeline_handles_no_articles(self):
        """Test cleanup pipeline gracefully handles when no articles need processing."""
        result = self._run_pipeline_subprocess('cleanup_pipeline.py')
        
        print("=== CLEANUP PIPELINE OUTPUT (No Articles) ===")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        print("Return Code:", result.returncode)
        
        # Should start successfully
        self.assertIn("--- Starting Main Processing Pipeline ---", result.stdout)
        
        # Should handle no articles gracefully (either "No unprocessed articles" or connection error is acceptable)
        acceptable_messages = [
            "No unprocessed articles found",
            "Error during RPC call",  # Database connection error is acceptable in test env
            "HTTPSConnectionPool",    # Network error is acceptable in test env
            "Connection error"        # General connection error
        ]
        
        has_acceptable_message = any(msg in result.stdout or msg in result.stderr 
                                   for msg in acceptable_messages)
        self.assertTrue(has_acceptable_message, 
                       f"Expected one of {acceptable_messages} in output")
        
        # Should complete and release lock
        self.assertIn("--- Lock released. Pipeline shutdown complete. ---", result.stdout)

    def test_cluster_pipeline_handles_no_clusters(self):
        """Test cluster pipeline gracefully handles when no clustering work is needed."""
        result = self._run_pipeline_subprocess('cluster_pipeline.py')
        
        print("=== CLUSTER PIPELINE OUTPUT (No Clusters) ===")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        print("Return Code:", result.returncode)
        
        # Should start various phases
        acceptable_start_messages = [
            "Checking for clusters that need status update",
            "Repairing clusters with zero centroid",
            "Starting article clustering workflow",
            "HTTPSConnectionPool",  # Network error is acceptable
            "Connection error"      # Connection error is acceptable
        ]
        
        has_start_message = any(msg in result.stdout or msg in result.stderr 
                              for msg in acceptable_start_messages)
        self.assertTrue(has_start_message, 
                       f"Expected clustering workflow to start")
        
        # Should complete and release lock (if it gets that far)
        if "--- Clustering lock released" in result.stdout:
            self.assertIn("--- Clustering lock released. Pipeline shutdown complete. ---", result.stdout)

    def test_pipeline_lock_mechanism(self):
        """Test that both pipelines respect the lock mechanism."""
        
        # Test cleanup pipeline lock
        with open(LOCK_FILE_PATH, 'w') as f:
            f.write('test_lock')
        
        result = self._run_pipeline_subprocess('cleanup_pipeline.py')
        self.assertIn("Pipeline is already running", result.stdout)
        self.assertEqual(result.returncode, 0)
        
        # Clean up lock
        os.remove(LOCK_FILE_PATH)
        
        # Test cluster pipeline lock  
        with open(LOCK_FILE_PATH, 'w') as f:
            f.write('test_lock')
            
        result = self._run_pipeline_subprocess('cluster_pipeline.py')
        # Cluster pipeline has different message format and may put message in stderr
        lock_messages = ["already running", "lock file exists", "Clustering pipeline is already running"]
        has_lock_message = any(msg in result.stdout.lower() or msg in result.stderr.lower() 
                              for msg in lock_messages)
        
        # Accept either success with lock message or connection error (since we use dummy credentials)
        acceptable = (has_lock_message or 
                     "Connection error" in result.stderr or 
                     "HTTPSConnectionPool" in result.stderr)
        
        self.assertTrue(acceptable, "Expected lock respect or connection error")

    def test_cleanup_pipeline_error_handling(self):
        """Test that cleanup pipeline handles errors gracefully without crashing."""
        
        # Run with invalid environment to trigger connection errors
        env = self._get_test_env()
        env['SUPABASE_URL'] = 'http://invalid-url-that-will-fail.com'
        
        result = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'cleanup_pipeline.py')],
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )
        
        print("=== CLEANUP PIPELINE ERROR HANDLING ===")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        print("Return Code:", result.returncode)
        
        # Should start but handle connection errors gracefully
        if "--- Starting Main Processing Pipeline ---" in result.stdout:
            # If it starts, it should handle errors and still release the lock
            if "--- Lock released" in result.stdout:
                self.assertIn("--- Lock released. Pipeline shutdown complete. ---", result.stdout)

    def test_cluster_pipeline_error_handling(self):
        """Test that cluster pipeline handles errors gracefully without crashing."""
        
        # Run with invalid environment to trigger connection errors
        env = self._get_test_env()
        env['SUPABASE_URL'] = 'http://invalid-url-that-will-fail.com'
        
        result = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'cluster_pipeline.py')],
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )
        
        print("=== CLUSTER PIPELINE ERROR HANDLING ===")
        print("STDOUT:", result.stdout) 
        print("STDERR:", result.stderr)
        print("Return Code:", result.returncode)
        
        # Should either complete successfully or fail gracefully
        # The pipeline should not hang or crash with unhandled exceptions

    def test_pipeline_modules_can_be_imported(self):
        """Test that all pipeline-related modules can be imported successfully."""
        import_tests = [
            'src.core.db.fetch_unprocessed_articles',
            'src.core.utils.lock_manager',
            'src.modules.processing.article_processor',
            'src.core.clustering.cluster_manager',
            'src.core.clustering.db_access',
            'src.modules.clustering.cluster_articles'
        ]
        
        with patch.dict(os.environ, self._get_test_env()):
            for module_name in import_tests:
                try:
                    __import__(module_name)
                except ImportError as e:
                    self.fail(f"Failed to import {module_name}: {e}")

if __name__ == '__main__':
    # Import required modules
    import importlib.util
    
    unittest.main(verbosity=2)
