import importlib
import os
import sys
from types import SimpleNamespace
from unittest import mock
import numpy as np

# Ensure modules can be reloaded with patched dependencies
@pytest.fixture(autouse=True)
def _prepend_parent_dir_to_syspath(monkeypatch):
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    monkeypatch.syspath_prepend(parent_dir)


import pytest


@pytest.fixture(autouse=True)
def _patch_env(monkeypatch):
    monkeypatch.setitem(sys.modules, "supabase", mock.MagicMock(create_client=lambda u, k: mock.Mock()))
    monkeypatch.setenv("SUPABASE_URL", "http://x")
    monkeypatch.setenv("SUPABASE_KEY", "y")



def reload_modules(monkeypatch):
    db_module = importlib.reload(importlib.import_module("core.clustering.db_access"))
    monkeypatch.setattr(db_module, "update_old_clusters_status", lambda: 0)
    manager_module = importlib.reload(importlib.import_module("core.clustering.cluster_manager"))
    return manager_module, db_module


def test_update_cluster(monkeypatch):
    cm_mod, db_mod = reload_modules(monkeypatch)
    updates = {}
    monkeypatch.setattr(cm_mod, "update_cluster_in_db", lambda cid, cent, cnt, isContent=False: updates.update(dict(cid=cid, centroid=cent, count=cnt, content=isContent)))

    manager = cm_mod.ClusterManager(check_old_clusters=False)
    old = np.array([1.0, 0.0], dtype=np.float32)
    new_vec = np.array([0.0, 1.0], dtype=np.float32)
    new_centroid, new_count = manager.update_cluster("c1", old, 2, new_vec)
    expected = (old * 2 + new_vec) / 3
    assert np.allclose(new_centroid, expected)
    assert new_count == 3
    assert updates["cid"] == "c1"
    assert np.allclose(updates["centroid"], expected)
    assert updates["count"] == 3
    assert updates["content"] is False


def test_create_cluster(monkeypatch):
    cm_mod, db_mod = reload_modules(monkeypatch)
    created = {}
    monkeypatch.setattr(cm_mod, "create_cluster_in_db", lambda cent, cnt: created.update(dict(centroid=cent, count=cnt)) or "cid123")
    manager = cm_mod.ClusterManager(check_old_clusters=False)
    vecs = [np.array([1,0], dtype=np.float32), np.array([0,1], dtype=np.float32)]
    cid, centroid, count = manager.create_cluster(vecs)
    assert cid == "cid123"
    assert np.allclose(centroid, np.array([0.5,0.5]))
    assert count == 2
    assert np.allclose(created["centroid"], centroid)
    assert created["count"] == 2


def test_find_best_cluster_match(monkeypatch):
    cm_mod, _ = reload_modules(monkeypatch)
    manager = cm_mod.ClusterManager(similarity_threshold=0.5, check_old_clusters=False)
    manager.clusters = [
        ("c1", np.array([1.0,0.0], dtype=np.float32), 2),
        ("c2", np.array([0.0,1.0], dtype=np.float32), 3),
    ]
    art_vec = np.array([0.8,0.2], dtype=np.float32)
    result = manager.find_best_cluster_match(art_vec)
    assert result and result[0] == "c1"


def test_find_best_pending_match_and_remove(monkeypatch):
    cm_mod, _ = reload_modules(monkeypatch)
    manager = cm_mod.ClusterManager(similarity_threshold=0.5, check_old_clusters=False)
    manager.add_to_pending(1, np.array([1.0,0.0], dtype=np.float32))
    manager.add_to_pending(2, np.array([0.0,1.0], dtype=np.float32))
    best = manager.find_best_pending_match(np.array([0.9,0.1], dtype=np.float32))
    assert best and best[0] == 1
    manager.remove_from_pending(best[0])
    assert 1 not in manager.pending_articles


class DummyTable:
    def __init__(self, data=None):
        self.data = data or []
        self.deleted_ids = []
    def select(self, *args, **kwargs):
        return self
    def eq(self, key, value):
        self.filter = value
        return self
    def execute(self):
        return SimpleNamespace(data=self.data)
    def delete(self):
        self.deleted = True
        return self

class DummySB:
    def __init__(self, articles):
        self.tables = {
            "SourceArticles": DummyTable(articles),
            "clusters": DummyTable([])
        }
    def table(self, name):
        return self.tables[name]


def test_check_and_merge_similar_clusters(monkeypatch):
    cm_mod, db_mod = reload_modules(monkeypatch)
    dummy_sb = DummySB([{"id": 10}])
    monkeypatch.setattr(db_mod, "sb", dummy_sb)
    updates = []
    monkeypatch.setattr(cm_mod, "update_cluster_in_db", lambda cid, cent, cnt, isContent=False: updates.append((cid, cent, cnt)))
    assignments = []
    monkeypatch.setattr(cm_mod, "assign_article_to_cluster", lambda aid, cid: assignments.append((aid, cid)))

    manager = cm_mod.ClusterManager(check_old_clusters=False)
    manager.clusters = [
        ("c1", np.array([1.0,0.0], dtype=np.float32), 2),
        ("c2", np.array([0.95,0.05], dtype=np.float32), 1),
    ]
    merged = manager.check_and_merge_similar_clusters(merge_threshold=0.9)
    assert merged
    assert len(manager.clusters) == 1
    assert updates
    assert assignments == [(10, "c1")]


def test_update_cluster_statuses(monkeypatch):
    cm_mod, db_mod = reload_modules(monkeypatch)
    monkeypatch.setattr(db_mod, "update_old_clusters_status", lambda: 5)
    manager = cm_mod.ClusterManager(check_old_clusters=False)
    result = manager.update_cluster_statuses()
    assert result == 5
