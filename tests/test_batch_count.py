import os
import sys
from types import SimpleNamespace
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

db_access = None

class DummyTable:
    def __init__(self, data):
        self.data = data
        self.upsert_calls = []
        self.update_calls = []
        self.delete_filters = []
    def select(self, *args, **kwargs):
        return self
    @property
    def not_(self):
        return self
    def is_(self, *args, **kwargs):
        return self
    def eq(self, *args, **kwargs):
        return self
    def in_(self, *args):
        self.delete_filters.append(args)
        return self
    def update(self, data):
        self.update_calls.append(data)
        return self
    def delete(self):
        self.delete_called = True
        return self
    def upsert(self, data, on_conflict=None):
        self.upsert_calls.append((data, on_conflict))
        return self
    def execute(self):
        return SimpleNamespace(data=self.data)

class DummySB:
    def __init__(self, clusters, articles):
        self.tables = {
            "clusters": DummyTable(clusters),
            "SourceArticles": DummyTable(articles),
        }
    def table(self, name):
        return self.tables[name]

def test_recalculate_member_counts_batch(monkeypatch):
    clusters = [
        {"cluster_id": "c1", "member_count": 1},
        {"cluster_id": "c2", "member_count": 5},
    ]
    articles = [
        {"id": 1, "cluster_id": "c1"},
        {"id": 2, "cluster_id": "c2"},
        {"id": 3, "cluster_id": "c2"},
        {"id": 4, "cluster_id": "c3"},
        {"id": 5, "cluster_id": "c3"},
    ]
    dummy = DummySB(clusters, articles)

    monkeypatch.setitem(sys.modules, "supabase", mock.MagicMock(create_client=lambda u, k: dummy))
    monkeypatch.setenv("SUPABASE_URL", "http://x")
    monkeypatch.setenv("SUPABASE_KEY", "y")

    import importlib
    import core.clustering.db_access as db_module
    db_access = importlib.reload(db_module)
    monkeypatch.setattr(db_access, "sb", dummy)

    discrepancies = db_access.recalculate_cluster_member_counts()

    upserts = dummy.tables["clusters"].upsert_calls
    deletes = dummy.tables["clusters"].delete_filters
    updates = dummy.tables["SourceArticles"].update_calls

    assert {c["cluster_id"] for c in upserts[0][0]} == {"c2", "c3"}
    assert any("cluster_id" in d[0] and "c1" in d[1] for d in deletes)
    assert updates and updates[0] == {"cluster_id": None}
    assert discrepancies.get("c2") == (5, 2)
