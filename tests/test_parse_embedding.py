import numpy as np
import pytest
from Tackle4LossContentExtraction.core.clustering.vector_utils import parse_embedding


@pytest.mark.parametrize(
    "input_str, expected",
    [
        ("[1.0, 2.0, 3.0]", np.array([1.0, 2.0, 3.0], dtype=np.float32)),
        ("1.0 2.0 3.0", np.array([1.0, 2.0, 3.0], dtype=np.float32)),
        pytest.param("foo, bar", pytest.raises(ValueError), id="invalid_input"),
    ],
)
def test_parse_embedding(input_str, expected):
    """Ensure ``parse_embedding`` parses valid strings and raises errors for
    invalid input."""

    # ``expected`` is either a numpy array or a ``pytest.raises`` context
    if isinstance(expected, np.ndarray):
        emb = parse_embedding(input_str)
        assert np.allclose(emb, expected)
    else:
        with expected:
            parse_embedding(input_str)
