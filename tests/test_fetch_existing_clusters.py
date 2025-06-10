import os
import sys
from types import SimpleNamespace
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

class DummyTable:
    def __init__(self, data):
        self.data = data
    def select(self, *args, **kwargs):
        return self
    def execute(self):
        return SimpleNamespace(data=self.data)

class DummySB:
    def __init__(self, clusters):
        self.tables = {
            "clusters": DummyTable(clusters),
        }
    def table(self, name):
        return self.tables[name]


def test_fetch_existing_clusters_skips_null(monkeypatch):
    clusters = [
        {"cluster_id": "c1", "centroid": None, "member_count": 2},
        {"cluster_id": "c2", "centroid": [0.1, 0.2], "member_count": 1},
    ]

    dummy = DummySB(clusters)
    monkeypatch.setitem(sys.modules, "supabase", mock.MagicMock(create_client=lambda u, k: dummy))
    monkeypatch.setenv("SUPABASE_URL", "http://x")
    monkeypatch.setenv("SUPABASE_KEY", "y")

    import importlib
    import core.clustering.db_access as db_module
    db_access = importlib.reload(db_module)
    monkeypatch.setattr(db_access, "sb", dummy)

    result = db_access.fetch_existing_clusters()
    assert len(result) == 1
    cid, centroid, count = result[0]
    assert cid == "c2"
    assert count == 1
