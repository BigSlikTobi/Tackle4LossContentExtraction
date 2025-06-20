import unittest
import os
import sys
import subprocess
import tempfile # For LOCK_FILE_PATH consistency

# Add the parent directory to sys.path to allow imports from core.utils
# This also helps the script locate core.utils.lock_manager when running the pipeline
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.utils.lock_manager import LOCK_FILE_PATH # Use the centralized lock file path

# Determine the path to the cleanup_pipeline.py script
PIPELINE_SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'cleanup_pipeline.py'))

class TestCleanupPipelineIntegration(unittest.TestCase):

    def setUp(self):
        """Ensure the lock file does not exist before each test."""
        if os.path.exists(LOCK_FILE_PATH):
            os.remove(LOCK_FILE_PATH)

    def tearDown(self):
        """Ensure the lock file is cleaned up after each test."""
        if os.path.exists(LOCK_FILE_PATH):
            os.remove(LOCK_FILE_PATH)

    def _run_pipeline(self, env=None):
        """Runs the cleanup_pipeline.py script as a subprocess."""
        # Pass the current python executable to run the script
        # This ensures that the script is run with the same interpreter and environment
        # Add PYTHONPATH to env to ensure imports work correctly in the subprocess
        process_env = os.environ.copy()

        # Add dummy Supabase environment variables for the subprocess
        process_env['SUPABASE_URL'] = 'http://dummy.url'
        # Use a structurally valid, but non-functional JWT for the key
        process_env['SUPABASE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c'
        # Add dummy OpenAI API key
        process_env['OPENAI_API_KEY'] = 'dummy_openai_key'
        # Add dummy Deepseek API key
        process_env['DEEPSEEK_API_KEY'] = 'dummy_deepseek_key'


        if env: # If other specific env vars were passed for a test
            process_env.update(env)

        # Ensure PYTHONPATH includes the project root for the subprocess
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

        print("--- Test: Runs Successfully Without Lock ---")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        print("Return Code:", result.returncode)

        self.assertIn("--- Starting Main Processing Pipeline ---", result.stdout)
        # Check for the "No unprocessed articles found" message as the db is empty
        self.assertIn("No unprocessed articles found.", result.stdout)
        self.assertIn("--- Lock released. Pipeline shutdown complete. ---", result.stdout)
        self.assertEqual(result.returncode, 0, f"Pipeline script failed with stderr: {result.stderr}")

        # The lock file should ideally be removed by the pipeline itself.
        # If the pipeline failed before release_lock, tearDown will clean it.
        self.assertFalse(os.path.exists(LOCK_FILE_PATH), "Lock file should be removed by the pipeline after successful execution.")

    def test_pipeline_exits_gracefully_if_lock_exists(self):
        """Test the pipeline exits gracefully if a lock file already exists."""
        # Manually create the lock file
        with open(LOCK_FILE_PATH, "w") as f:
            f.write("locked")
        self.assertTrue(os.path.exists(LOCK_FILE_PATH), "Lock file should be manually created for this test.")

        result = self._run_pipeline()

        print("--- Test: Exits Gracefully If Lock Exists ---")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        print("Return Code:", result.returncode)

        self.assertIn("Pipeline is already running. Exiting.", result.stdout)
        self.assertEqual(result.returncode, 0, f"Pipeline script failed or did not exit as expected. Stderr: {result.stderr}")

        # Ensure the manually created lock file is still present (pipeline shouldn't remove it)
        self.assertTrue(os.path.exists(LOCK_FILE_PATH), "Lock file should still exist as pipeline should not have acquired or released it.")

if __name__ == '__main__':
    unittest.main()
