import os
import tempfile

LOCK_FILE_NAME = "pipeline.lock"
LOCK_FILE_PATH = os.path.join(tempfile.gettempdir(), LOCK_FILE_NAME)

def acquire_lock():
    """
    Acquires a lock by creating a lock file.

    Returns:
        bool: True if the lock was acquired, False otherwise.
    """
    if os.path.exists(LOCK_FILE_PATH):
        return False
    else:
        try:
            with open(LOCK_FILE_PATH, "w") as f:
                pass  # Just create the file
            return True
        except OSError:
            # Handle potential errors during file creation, though unlikely for a simple case.
            return False

def release_lock():
    """
    Releases the lock by deleting the lock file.
    """
    try:
        if os.path.exists(LOCK_FILE_PATH):
            os.remove(LOCK_FILE_PATH)
    except OSError:
        # Handle potential errors during file deletion.
        # Depending on requirements, might want to log this or raise an exception.
        pass
