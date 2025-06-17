import numpy as np
import pytest
from core.clustering.vector_utils import parse_embedding


@pytest.mark.parametrize(
    "input_str, expected",
    [
        ("[1.0, 2.0, 3.0]", np.array([1.0, 2.0, 3.0], dtype=np.float32)),
        ("1.0 2.0 3.0", np.array([1.0, 2.0, 3.0], dtype=np.float32)),
        pytest.param("foo, bar", pytest.raises(ValueError), id="invalid_input"),
    ],
)
def test_parse_embedding(input_str, expected):
    if isinstance(expected, pytest.raises):
        with expected:
            parse_embedding(input_str)
    else:
        emb = parse_embedding(input_str)
        assert np.allclose(emb, expected)
