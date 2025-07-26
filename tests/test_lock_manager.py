import unittest
import os
import sys

# Add the parent directory to sys.path to allow imports from src.core.utils
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.utils.lock_manager import acquire_lock, release_lock, LOCK_FILE_PATH

class TestLockManager(unittest.TestCase):

    def setUp(self):
        """Ensure the lock file does not exist before each test."""
        if os.path.exists(LOCK_FILE_PATH):
            os.remove(LOCK_FILE_PATH)

    def tearDown(self):
        """Ensure the lock file is cleaned up after each test."""
        if os.path.exists(LOCK_FILE_PATH):
            os.remove(LOCK_FILE_PATH)

    def test_acquire_lock_success(self):
        """Test that acquire_lock returns True and creates the lock file."""
        self.assertTrue(acquire_lock(), "acquire_lock should return True when no lock exists.")
        self.assertTrue(os.path.exists(LOCK_FILE_PATH), "Lock file should be created.")

    def test_acquire_lock_failure_if_already_locked(self):
        """Test that acquire_lock returns False if the lock file already exists."""
        # Create a dummy lock file
        with open(LOCK_FILE_PATH, "w") as f:
            f.write("locked")

        self.assertFalse(acquire_lock(), "acquire_lock should return False when lock already exists.")
        # Ensure the dummy lock file is still there (acquire_lock shouldn't delete it)
        self.assertTrue(os.path.exists(LOCK_FILE_PATH))

    def test_release_lock_success(self):
        """Test that release_lock deletes the lock file."""
        # Create a dummy lock file
        with open(LOCK_FILE_PATH, "w") as f:
            f.write("locked")

        release_lock()
        self.assertFalse(os.path.exists(LOCK_FILE_PATH), "Lock file should be deleted by release_lock.")

    def test_release_lock_no_error_if_not_exists(self):
        """Test that release_lock does not raise an error if the lock file does not exist."""
        # Ensure lock file does not exist
        if os.path.exists(LOCK_FILE_PATH):
            os.remove(LOCK_FILE_PATH)

        try:
            release_lock()
        except Exception as e:
            self.fail(f"release_lock raised an unexpected exception: {e}")

if __name__ == '__main__':
    unittest.main()
