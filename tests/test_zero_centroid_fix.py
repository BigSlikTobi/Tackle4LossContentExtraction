import os
import sys
from types import SimpleNamespace
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

class DummyTable:
    def __init__(self, data):
        self.data = data
        self.filters = []
    def select(self, *args, **kwargs):
        return self
    def eq(self, key, value):
        self.filters.append((key, value))
        return self
    def execute(self):
        result = self.data
        for key, value in self.filters:
            result = [row for row in result if row.get(key) == value]
        self.filters = []
        return SimpleNamespace(data=result)

class DummySB:
    def __init__(self, clusters, articles):
        self.tables = {
            "clusters": DummyTable(clusters),
            "SourceArticles": DummyTable(articles),
        }
    def table(self, name):
        return self.tables[name]

def test_repair_zero_centroid_clusters(monkeypatch):
    clusters = [
        {"cluster_id": "c1", "centroid": [0.0, 0.0, 0.0]},
        {"cluster_id": "c2", "centroid": [0.1, 0.2, 0.3]},
    ]
    articles = [
        {"id": 1, "cluster_id": "c1", "ArticleVector": [{"embedding": "[1,0,0]"}]},
        {"id": 2, "cluster_id": "c1", "ArticleVector": [{"embedding": "[0,1,0]"}]},
        {"id": 3, "cluster_id": "c2", "ArticleVector": [{"embedding": "[0.1,0.2,0.3]"}]},
    ]

    dummy = DummySB(clusters, articles)
    monkeypatch.setitem(sys.modules, "supabase", mock.MagicMock(create_client=lambda u, k: dummy))
    monkeypatch.setenv("SUPABASE_URL", "http://x")
    monkeypatch.setenv("SUPABASE_KEY", "y")

    import importlib
    import core.clustering.db_access as db_module
    db_access = importlib.reload(db_module)
    monkeypatch.setattr(db_access, "sb", dummy)

    updates = []
    def dummy_update(cid, centroid, count, isContent=False):
        updates.append((cid, centroid.tolist(), count))
    monkeypatch.setattr(db_access, "update_cluster_in_db", dummy_update)

    fixed = db_access.repair_zero_centroid_clusters()

    assert fixed == ["c1"]
    assert updates
    cid, centroid, count = updates[0]
    assert cid == "c1"
    assert count == 2
    assert centroid == [0.5, 0.5, 0.0]

def test_repair_null_centroid_clusters(monkeypatch):
    clusters = [
        {"cluster_id": "c1", "centroid": None},
        {"cluster_id": "c2", "centroid": [0.1, 0.2, 0.3]},
    ]
    articles = [
        {"id": 1, "cluster_id": "c1", "ArticleVector": [{"embedding": "[1,0,0]"}]},
        {"id": 2, "cluster_id": "c1", "ArticleVector": [{"embedding": "[0,1,0]"}]},
    ]

    dummy = DummySB(clusters, articles)
    monkeypatch.setitem(sys.modules, "supabase", mock.MagicMock(create_client=lambda u, k: dummy))
    monkeypatch.setenv("SUPABASE_URL", "http://x")
    monkeypatch.setenv("SUPABASE_KEY", "y")

    import importlib
    import core.clustering.db_access as db_module
    db_access = importlib.reload(db_module)
    monkeypatch.setattr(db_access, "sb", dummy)

    updates = []
    def dummy_update(cid, centroid, count, isContent=False):
        updates.append((cid, centroid.tolist(), count))
    monkeypatch.setattr(db_access, "update_cluster_in_db", dummy_update)

    fixed = db_access.repair_zero_centroid_clusters()

    assert fixed == ["c1"]
    assert updates
    cid, centroid, count = updates[0]
    assert cid == "c1"
    assert count == 2
    assert centroid == [0.5, 0.5, 0.0]

