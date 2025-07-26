"""
This module provides a simple file-based locking mechanism to prevent concurrent access
to a resource (e.g., a pipeline) by multiple processes.
It uses a lock file to indicate whether the resource is currently in use.
"""

import os
import tempfile

LOCK_FILE_NAME = "pipeline.lock"
LOCK_FILE_PATH = os.path.join(tempfile.gettempdir(), LOCK_FILE_NAME)

def acquire_lock():
    """
    Acquires a lock by creating a lock file.
    This function checks if the lock file exists. If it does not exist, it creates the file to indicate
    that the resource is locked. If the file already exists, it means another process is using the resource.
    Args:
        None        
    Returns:
        bool: True if the lock was acquired, False otherwise.
    Raises:
        OSError: If there is an error creating the lock file.   
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
    This function removes the lock file to indicate that the resource is no longer in use.
    Args:
        None        
    Returns:
        None
    Raises:
        OSError: If there is an error deleting the lock file.
    """
    try:
        if os.path.exists(LOCK_FILE_PATH):
            os.remove(LOCK_FILE_PATH)
    except OSError:
        # Handle potential errors during file deletion.
        # Depending on requirements, might want to log this or raise an exception.
        pass
