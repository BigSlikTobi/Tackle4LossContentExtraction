import os
import numpy as np
import importlib
from unittest import mock

os.environ.setdefault("SUPABASE_URL", "http://x")
os.environ.setdefault("SUPABASE_KEY", "y")
os.environ.setdefault("OPENAI_API_KEY", "testkey")

with mock.patch("supabase.create_client", return_value=mock.Mock()), \
     mock.patch("openai.OpenAI", return_value=mock.Mock()):
    ce = importlib.import_module("core.utils.create_embeddings")


def test_normalize_embedding_unit_vector():
    result = ce.normalize_embedding([3, 4])
    assert np.allclose(result, np.array([0.6, 0.8]))


def test_normalize_embedding_zero_vector():
    result = ce.normalize_embedding([0, 0])
    assert result == [0, 0]
