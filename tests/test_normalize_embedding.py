import os
import sys
import numpy as np
import importlib
from types import ModuleType
from unittest import mock
import pytest

os.environ.setdefault("SUPABASE_URL", "http://x")
os.environ.setdefault("SUPABASE_KEY", "y")
os.environ.setdefault("OPENAI_API_KEY", "testkey")

@pytest.fixture
def ce_fixture():
    supabase_mock = ModuleType("supabase")
    supabase_mock.create_client = mock.Mock(return_value=mock.Mock())
    supabase_mock.Client = mock.Mock()
    openai_mock = ModuleType("openai")
    openai_mock.OpenAI = mock.Mock(return_value=mock.Mock())

    with mock.patch.dict(sys.modules, {"supabase": supabase_mock, "openai": openai_mock}):
        ce = importlib.import_module("Tackle4LossContentExtraction.core.utils.create_embeddings")
        yield ce


def test_normalize_embedding_unit_vector(ce_fixture):
    result = ce_fixture.normalize_embedding([3, 4])
    assert np.allclose(result, np.array([0.6, 0.8]))


def test_normalize_embedding_zero_vector(ce_fixture):
    result = ce_fixture.normalize_embedding([0, 0])
    assert np.allclose(result, np.array([0, 0]))
