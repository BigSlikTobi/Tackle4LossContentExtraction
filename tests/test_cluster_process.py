import importlib
import sys
import os
from unittest import mock
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))


def test_run_clustering_process_creates_cluster(monkeypatch):
    # Fake supabase client to avoid real initialization
    dummy_sb = mock.MagicMock()
    # Make the resp.data iterable to avoid the Mock iteration error
    dummy_resp = mock.MagicMock()
    dummy_resp.data = []  # Empty list instead of Mock
    dummy_sb.table.return_value.select.return_value.not_.return_value.execute.return_value = dummy_resp
    
    monkeypatch.setitem(sys.modules, "supabase", mock.MagicMock(create_client=lambda u, k: dummy_sb))
    monkeypatch.setenv("SUPABASE_URL", "http://x")
    monkeypatch.setenv("SUPABASE_KEY", "y")

    # Reload modules with patched supabase
    db_access = importlib.reload(importlib.import_module("src.core.clustering.db_access"))
    
    # Properly mock the update_old_clusters_status to return a number
    def mock_update_old_clusters_status():
        return 0
    monkeypatch.setattr(db_access, "update_old_clusters_status", mock_update_old_clusters_status)
    
    cluster_manager = importlib.reload(importlib.import_module("src.core.clustering.cluster_manager"))
    cluster_articles = importlib.reload(importlib.import_module("src.modules.clustering.cluster_articles"))

    # Use 768-dimensional vectors to match the expected dimensions
    base_vector = np.random.random(768).astype(np.float32)
    articles = [
        (1, base_vector),
        (2, base_vector + 0.1 * np.random.random(768).astype(np.float32)),  # Similar vector
    ]

    monkeypatch.setattr(db_access, "fetch_unclustered_articles", lambda: articles)
    monkeypatch.setattr(db_access, "fetch_existing_clusters", lambda: [])
    monkeypatch.setattr(cluster_articles, "fetch_unclustered_articles", lambda: articles)
    monkeypatch.setattr(cluster_articles, "fetch_existing_clusters", lambda: [])

    created = []
    def fake_create_cluster_in_db(centroid, count):
        created.append((centroid, count))
        return "clusterX"

    assignments = []
    def fake_batch(assignments_list):
        assignments.extend(assignments_list)

    monkeypatch.setattr(db_access, "create_cluster_in_db", fake_create_cluster_in_db)
    monkeypatch.setattr(db_access, "batch_assign_articles_to_cluster", fake_batch)
    monkeypatch.setattr(db_access, "update_cluster_in_db", lambda cid, c, n, isContent=False: None)
    monkeypatch.setattr(cluster_articles, "batch_assign_articles_to_cluster", fake_batch)

    monkeypatch.setattr(cluster_manager, "create_cluster_in_db", fake_create_cluster_in_db)
    monkeypatch.setattr(cluster_manager, "batch_assign_articles_to_cluster", fake_batch)
    monkeypatch.setattr(cluster_manager, "update_cluster_in_db", lambda cid, c, n, isContent=False: None)

    cluster_articles.run_clustering_process(similarity_threshold=0.8, merge_threshold=0.9)

    assert created and created[0][1] == 2
    assert assignments == [(1, "clusterX"), (2, "clusterX")]
