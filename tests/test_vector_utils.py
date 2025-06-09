import numpy as np
from core.clustering.vector_utils import cosine_similarity


def test_cosine_similarity_with_empty_inputs():
    assert cosine_similarity(np.array([]), np.array([])) == 0.0


def test_cosine_similarity_with_scalar_inputs():
    assert cosine_similarity(np.array(0.5), np.array(0.5)) == 0.0
