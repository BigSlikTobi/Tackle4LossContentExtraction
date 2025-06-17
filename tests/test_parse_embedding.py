import numpy as np
import pytest
from core.clustering.vector_utils import parse_embedding


def test_parse_embedding_brackets():
    emb = parse_embedding("[1.0, 2.0, 3.0]")
    assert np.allclose(emb, np.array([1.0, 2.0, 3.0], dtype=np.float32))


def test_parse_embedding_spaces():
    emb = parse_embedding("1.0 2.0 3.0")
    assert np.allclose(emb, np.array([1.0, 2.0, 3.0], dtype=np.float32))


def test_parse_embedding_invalid():
    with pytest.raises(ValueError):
        parse_embedding("foo, bar")
