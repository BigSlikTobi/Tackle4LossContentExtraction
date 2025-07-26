import unittest
import os
import sys
import subprocess
import time
import threading

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from src.core.utils.lock_manager import LOCK_FILE_PATH

CLEANUP_PIPELINE_SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'cleanup_pipeline.py'))
CLUSTER_PIPELINE_SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'cluster_pipeline.py'))

class TestConcurrentPipelineRuns(unittest.TestCase):

    def setUp(self):
        """Ensure the lock file does not exist before each test."""
        if os.path.exists(LOCK_FILE_PATH):
            os.remove(LOCK_FILE_PATH)
        self.assertFalse(os.path.exists(LOCK_FILE_PATH), "Lock file should be cleaned up before test.")

    def tearDown(self):
        """Ensure the lock file is cleaned up after each test."""
        if os.path.exists(LOCK_FILE_PATH):
            os.remove(LOCK_FILE_PATH)
        self.assertFalse(os.path.exists(LOCK_FILE_PATH), "Lock file should be cleaned up after test.")

    def _get_pipeline_env(self):
        """Prepares the environment variables for pipeline execution."""
        env = os.environ.copy()
        env['PYTHONPATH'] = os.path.abspath(os.path.join(os.path.dirname(__file__), '..')) + (os.pathsep + env.get('PYTHONPATH', ''))
        env['SUPABASE_URL'] = 'http://dummy.url'
        env['SUPABASE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c'
        env['OPENAI_API_KEY'] = 'dummy_openai_key'
        env['DEEPSEEK_API_KEY'] = 'dummy_deepseek_key'
        return env

    def _run_pipeline_instance(self, script_path, env, results_list, instance_id):
        """Runs a single pipeline instance and stores its output."""
        # print(f"Starting instance {instance_id} of {script_path} at {time.time()}")
        process = subprocess.Popen(
            [sys.executable, script_path],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        # print(f"Instance {instance_id} of {script_path} finished at {time.time()} with code {process.returncode}")
        # print(f"Instance {instance_id} STDOUT: {stdout}")
        # print(f"Instance {instance_id} STDERR: {stderr}")

        result_data = {
            "id": instance_id,
            "stdout": stdout,
            "stderr": stderr,
            "returncode": process.returncode
        }

        # Debug prints to see what each instance is doing
        print(f"DEBUG: Instance {instance_id} ({os.path.basename(script_path)}) finished.")
        print(f"DEBUG: Instance {instance_id} RC: {result_data['returncode']}")
        print(f"DEBUG: Instance {instance_id} STDOUT:\n{result_data['stdout']}")
        print(f"DEBUG: Instance {instance_id} STDERR:\n{result_data['stderr']}\n--------------------")

        # Store results at the correct index, assuming results_list is pre-sized
        if isinstance(results_list, list) and instance_id < len(results_list):
            results_list[instance_id] = result_data
        else:
            # This case should ideally not be hit if tests pre-size results_list
            # However, ensure it's syntactically correct if ever reached.
            print(f"Warning: results_list not pre-sized or instance_id out of bounds for instance {instance_id}. Appending.")
            results_list.append(result_data)


    def analyze_concurrent_results(self, acquirer_result, locked_out_result,
                                 primary_success_msg, lock_acquired_early_msg, locked_out_msg,
                                 primary_output_type, locked_out_output_type,
                                 running_instance_expected_rc_func):
        """
        Analyzes the results from two concurrent pipeline runs where one is expected to acquire the lock
        and the other is expected to be locked out.
        """
        self.assertIsNotNone(acquirer_result, "Acquirer result should not be None")
        self.assertIsNotNone(locked_out_result, "Locked-out result should not be None")

        # Check acquirer
        acquirer_msgs_ok = (lock_acquired_early_msg in acquirer_result[primary_output_type] and \
                            primary_success_msg in acquirer_result[primary_output_type])
        acquirer_rc_ok = running_instance_expected_rc_func(acquirer_result["returncode"]) if running_instance_expected_rc_func else True

        self.assertTrue(acquirer_msgs_ok, f"Acquirer instance (id={acquirer_result['id']}) did not show expected messages.\nSTDOUT: {acquirer_result['stdout']}\nSTDERR: {acquirer_result['stderr']}")
        self.assertTrue(acquirer_rc_ok, f"Acquirer instance (id={acquirer_result['id']}) had unexpected return code: {acquirer_result['returncode']}.\nSTDOUT: {acquirer_result['stdout']}\nSTDERR: {acquirer_result['stderr']}")

        # Check locked-out instance
        locked_out_msg_ok = locked_out_msg in locked_out_result[locked_out_output_type]
        locked_out_rc_ok = locked_out_result["returncode"] == 0

        self.assertTrue(locked_out_msg_ok, f"Locked-out instance (id={locked_out_result['id']}) did not show expected message.\nSTDOUT: {locked_out_result['stdout']}\nSTDERR: {locked_out_result['stderr']}")
        self.assertTrue(locked_out_rc_ok, f"Locked-out instance (id={locked_out_result['id']}) had unexpected return code: {locked_out_result['returncode']}.\nSTDOUT: {locked_out_result['stdout']}\nSTDERR: {locked_out_result['stderr']}")

    # Removed _wait_for_lock as it's not suitable for the fast execution of pipelines

    def test_concurrent_cleanup_pipelines(self):
        """Test concurrent execution of cleanup_pipeline.py by simulating a lock."""
        env = self._get_pipeline_env()

        # Run Instance 1 (Acquirer - should run normally and release lock)
        # Ensure no lock at the very start for this one
        if os.path.exists(LOCK_FILE_PATH): os.remove(LOCK_FILE_PATH)

        results_acquirer_list = [None]
        thread_acquirer = threading.Thread(target=self._run_pipeline_instance, args=(CLEANUP_PIPELINE_SCRIPT_PATH, env, results_acquirer_list, 0))
        thread_acquirer.start()
        thread_acquirer.join() # Wait for it to complete fully
        acquirer_result = results_acquirer_list[0]

        # Assert Instance 1 ran as expected
        self.assertIn("--- Starting Main Processing Pipeline ---", acquirer_result['stdout'])
        self.assertIn("--- Lock released. Pipeline shutdown complete. ---", acquirer_result['stdout'])
        self.assertEqual(acquirer_result['returncode'], 0)
        self.assertFalse(os.path.exists(LOCK_FILE_PATH), "Acquirer instance should have removed the lock.")

        # Run Instance 2 (Locked out - should detect lock and exit)
        # Manually create the lock file to simulate it being held
        with open(LOCK_FILE_PATH, "w") as f:
            f.write("test_lock")
        self.assertTrue(os.path.exists(LOCK_FILE_PATH))

        results_locked_out_list = [None]
        thread_locked_out = threading.Thread(target=self._run_pipeline_instance, args=(CLEANUP_PIPELINE_SCRIPT_PATH, env, results_locked_out_list, 0))
        thread_locked_out.start()
        thread_locked_out.join()
        locked_out_result = results_locked_out_list[0]

        # Assert Instance 2 was locked out
        self.assertIn("Pipeline is already running. Exiting.", locked_out_result['stdout'])
        self.assertEqual(locked_out_result['returncode'], 0)
        self.assertTrue(os.path.exists(LOCK_FILE_PATH), "Lock file should still exist as locked-out instance should not remove it.")

        # Final cleanup of the manually created lock
        os.remove(LOCK_FILE_PATH)

    def test_concurrent_cluster_pipelines(self):
        """Test concurrent execution of cluster_pipeline.py by simulating a lock."""
        env = self._get_pipeline_env()

        # Run Instance 1 (Acquirer - should run normally and release lock)
        if os.path.exists(LOCK_FILE_PATH): os.remove(LOCK_FILE_PATH)

        results_acquirer_list = [None]
        thread_acquirer = threading.Thread(target=self._run_pipeline_instance, args=(CLUSTER_PIPELINE_SCRIPT_PATH, env, results_acquirer_list, 0))
        thread_acquirer.start()
        thread_acquirer.join()
        acquirer_result = results_acquirer_list[0]

        # Assert Instance 1 ran as expected (crashes but releases lock)
        self.assertIn("Checking for clusters that need status update...", acquirer_result['stderr'])
        self.assertIn("--- Clustering lock released. Pipeline shutdown complete. ---", acquirer_result['stderr'])
        self.assertNotEqual(acquirer_result['returncode'], 0) # Expecting crash due to dummy DB
        self.assertFalse(os.path.exists(LOCK_FILE_PATH), "Acquirer instance should have removed the lock.")

        # Run Instance 2 (Locked out - should detect lock and exit)
        with open(LOCK_FILE_PATH, "w") as f:
            f.write("test_lock")
        self.assertTrue(os.path.exists(LOCK_FILE_PATH))

        results_locked_out_list = [None]
        thread_locked_out = threading.Thread(target=self._run_pipeline_instance, args=(CLUSTER_PIPELINE_SCRIPT_PATH, env, results_locked_out_list, 0))
        thread_locked_out.start()
        thread_locked_out.join()
        locked_out_result = results_locked_out_list[0]

        # Assert Instance 2 was locked out
        self.assertIn("Clustering pipeline is already running or lock file exists. Exiting.", locked_out_result['stderr'])
        self.assertEqual(locked_out_result['returncode'], 0)
        self.assertTrue(os.path.exists(LOCK_FILE_PATH), "Lock file should still exist as locked-out instance should not remove it.")

        # Final cleanup
        os.remove(LOCK_FILE_PATH)


if __name__ == '__main__':
    unittest.main()
