"""
Vector manipulation utilities for article clustering.
"""

import numpy as np
import logging
from typing import List

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_embedding(embedding_str: str) -> np.ndarray:
    """Parse embedding string from database into numpy array.
    
    Args:
        embedding_str: String representation of embedding vector
        
    Returns:
        numpy.ndarray: The embedding as a numpy array
        
    Raises:
        ValueError: If the embedding string cannot be parsed
    """
    try:
        # Handle both array-like strings and JSON-formatted strings
        if embedding_str.startswith('[') and embedding_str.endswith(']'):
            # Strip brackets and split by comma
            values = [float(x.strip()) for x in embedding_str.strip('[]').split(',')]
            return np.array(values, dtype=np.float32)
        else:
            # Try parsing as space-separated values
            values = [float(x) for x in embedding_str.strip().split()]
            return np.array(values, dtype=np.float32)
    except Exception as e:
        logger.error(f"Failed to parse embedding string: {str(e)}")
        raise ValueError(f"Invalid embedding format: {embedding_str[:50]}...")

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    The function is tolerant of empty or zero-dimensional arrays and will simply
    return ``0.0`` in those cases. If the vectors differ in length by a factor of
    two, the longer vector is downsampled to match the shorter one. Any other
    dimensional mismatch results in ``ValueError``.
    """

    a = np.asarray(a)
    b = np.asarray(b)

    if a.ndim == 0 or b.ndim == 0:
        logger.warning("One or both vectors are scalar. Returning similarity as 0.0.")
        return 0.0

    a = a.ravel()
    b = b.ravel()

    if a.size == 0 or b.size == 0:
        logger.warning("One or both vectors are empty. Returning similarity as 0.0.")
        return 0.0

    # Handle dimension mismatch
    if a.size != b.size:
        if a.size == b.size * 2:
            a = a[::2]
        elif b.size == a.size * 2:
            b = b[::2]
        else:
            raise ValueError(f"Incompatible dimensions: {a.size} and {b.size}")
    
    # Compute norms
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    
    # Check for zero norms
    if norm_a == 0 or norm_b == 0:
        logger.warning("One or both vectors have zero norm. Returning similarity as 0.0.")
        return 0.0
    
    return float(np.dot(a, b) / (norm_a * norm_b))

def normalize_vector_dimensions(vec_a: np.ndarray, vec_b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Normalize two vectors to have the same dimensions by downsampling the larger one."""
    if vec_a.shape[0] == vec_b.shape[0]:
        return vec_a, vec_b
    
    # If vec_a is twice as long as vec_b, downsample vec_a
    if vec_a.shape[0] == vec_b.shape[0] * 2:
        return vec_a[::2], vec_b
    
    # If vec_b is twice as long as vec_a, downsample vec_b
    if vec_b.shape[0] == vec_a.shape[0] * 2:
        return vec_a, vec_b[::2]
    
    raise ValueError(f"Incompatible dimensions: {vec_a.shape[0]} and {vec_b.shape[0]}")
