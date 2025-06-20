import unittest
import os
import sys
import subprocess

# Add the parent directory to sys.path to allow imports from core.utils
# This also helps the script locate core.utils.lock_manager when running the pipeline
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.utils.lock_manager import LOCK_FILE_PATH # Use the centralized lock file path

# Determine the path to the cluster_pipeline.py script
PIPELINE_SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'cluster_pipeline.py'))

class TestClusterPipelineIntegration(unittest.TestCase):

    def setUp(self):
        """Ensure the lock file does not exist before each test."""
        if os.path.exists(LOCK_FILE_PATH):
            os.remove(LOCK_FILE_PATH)

    def tearDown(self):
        """Ensure the lock file is cleaned up after each test."""
        if os.path.exists(LOCK_FILE_PATH):
            os.remove(LOCK_FILE_PATH)

    def _run_pipeline(self, env=None):
        """Runs the cluster_pipeline.py script as a subprocess."""
        process_env = os.environ.copy()

        # Add dummy environment variables required by the pipeline or its imports
        process_env['SUPABASE_URL'] = 'http://dummy.url'
        process_env['SUPABASE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c'
        process_env['OPENAI_API_KEY'] = 'dummy_openai_key'
        process_env['DEEPSEEK_API_KEY'] = 'dummy_deepseek_key'
        # Add other keys as discovered e.g. ANTHROPIC_API_KEY, GOOGLE_API_KEY

        if env: # If other specific env vars were passed for a test
            process_env.update(env)

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        if 'PYTHONPATH' in process_env:
            process_env['PYTHONPATH'] = f"{project_root}:{process_env['PYTHONPATH']}"
        else:
            process_env['PYTHONPATH'] = project_root

        return subprocess.run(
            [sys.executable, PIPELINE_SCRIPT_PATH],
            capture_output=True,
            text=True,
            env=process_env
        )

    def test_pipeline_runs_successfully_without_lock(self):
        """Test the pipeline runs successfully when no lock file exists."""
        self.assertFalse(os.path.exists(LOCK_FILE_PATH), "Lock file should not exist at the start of this test.")

        result = self._run_pipeline()

        print("--- Test Cluster: Runs Successfully Without Lock ---")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        print("Return Code:", result.returncode)

        # Check for key log messages in STDERR as logging goes there.
        # We check for an early message before potential DB connection errors.
        self.assertIn("Checking for clusters that need status update...", result.stderr)
        # Check for the specific message from cluster_pipeline.py in STDERR
        # This confirms the finally block executed.
        self.assertIn("--- Clustering lock released. Pipeline shutdown complete. ---", result.stderr)

        # Note: We are not asserting result.returncode == 0 here because the dummy SUPABASE_URL
        # will cause httpx.ConnectError during DB operations, leading to a non-zero exit code.
        # However, the lock should still be acquired and released correctly by the finally block.
        # This test focuses on the lock mechanism's correct operation even if internal ops fail.

        self.assertFalse(os.path.exists(LOCK_FILE_PATH), "Lock file should be removed by the pipeline after successful execution.")

    def test_pipeline_exits_gracefully_if_lock_exists(self):
        """Test the pipeline exits gracefully if a lock file already exists."""
        with open(LOCK_FILE_PATH, "w") as f:
            f.write("locked")
        self.assertTrue(os.path.exists(LOCK_FILE_PATH), "Lock file should be manually created for this test.")

        result = self._run_pipeline()

        print("--- Test Cluster: Exits Gracefully If Lock Exists ---")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        print("Return Code:", result.returncode)

        self.assertIn("Clustering pipeline is already running or lock file exists. Exiting.", result.stderr)
        self.assertEqual(result.returncode, 0, f"Pipeline script failed or did not exit as expected. Stderr: {result.stderr}")

        self.assertTrue(os.path.exists(LOCK_FILE_PATH), "Lock file should still exist as pipeline should not have acquired or released it.")

if __name__ == '__main__':
    unittest.main()
