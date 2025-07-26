import os
import sys
from types import SimpleNamespace
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

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
    import src.core.clustering.db_access as db_module
    db_access = importlib.reload(db_module)
    monkeypatch.setattr(db_access, "sb", dummy)

    discrepancies = db_access.recalculate_cluster_member_counts()

    upserts = dummy.tables["clusters"].upsert_calls
    updates = dummy.tables["clusters"].update_calls
    deletes = dummy.tables["clusters"].delete_filters
    article_updates = dummy.tables["SourceArticles"].update_calls

    # Check that c3 was upserted (new cluster) and c2 was updated (existing cluster)
    assert len(upserts) == 1 and len(upserts[0][0]) == 1
    assert upserts[0][0][0]["cluster_id"] == "c3"
    assert len(updates) == 1
    assert updates[0]["member_count"] == 2  # c2 count updated from 5 to 2
    assert any("cluster_id" in d[0] and "c1" in d[1] for d in deletes)
    assert article_updates and article_updates[0] == {"cluster_id": None}
    assert discrepancies.get("c2") == (5, 2)
