import numpy as np
from src.core.clustering.vector_utils import cosine_similarity


def test_cosine_similarity_with_empty_inputs():
    assert cosine_similarity(np.array([]), np.array([])) == 0.0


def test_cosine_similarity_with_scalar_inputs():
    assert cosine_similarity(np.array(0.5), np.array(0.5)) == 0.0

from src.core.clustering.vector_utils import parse_embedding
import pytest


def test_parse_embedding_bracket_string():
    arr = parse_embedding("[1.0, 2.0, 3.0]")
    assert np.allclose(arr, [1.0, 2.0, 3.0])


def test_parse_embedding_space_separated():
    arr = parse_embedding("1.0 2.0 3.0")
    assert np.allclose(arr, [1.0, 2.0, 3.0])


def test_parse_embedding_invalid():
    with pytest.raises(ValueError):
        parse_embedding("invalid")
