"""Tests for ML clustering."""
import pytest
import numpy as np
from scipy.sparse import csr_matrix


@pytest.fixture
def clustering_dataset():
    return csr_matrix(np.random.rand(20, 50))


class TestHypotheticalClusterer:
    def test_fit_kmeans(self, clustering_dataset):
        from src.ml.clustering import HypotheticalClusterer
        clusterer = HypotheticalClusterer(method="kmeans")
        labels = clusterer.fit(clustering_dataset, n_clusters=3)
        assert clusterer.is_trained
        assert len(labels) == 20

    def test_predict_cluster(self, clustering_dataset):
        from src.ml.clustering import HypotheticalClusterer
        clusterer = HypotheticalClusterer(method="kmeans")
        clusterer.fit(clustering_dataset, n_clusters=3)
        cluster = clusterer.predict_cluster(clustering_dataset[:1])
        assert isinstance(cluster, int)

    def test_cluster_summary(self, clustering_dataset):
        from src.ml.clustering import HypotheticalClusterer
        clusterer = HypotheticalClusterer(method="kmeans")
        clusterer.fit(clustering_dataset, n_clusters=3)
        summary = clusterer.get_cluster_summary()
        assert isinstance(summary, dict)

    def test_visualize(self, clustering_dataset):
        from src.ml.clustering import HypotheticalClusterer
        clusterer = HypotheticalClusterer(method="kmeans")
        clusterer.fit(clustering_dataset, n_clusters=3)
        table = clusterer.visualize_clusters()
        assert "Cluster" in table

    def test_save_load(self, clustering_dataset, tmp_path):
        from src.ml.clustering import HypotheticalClusterer
        clusterer = HypotheticalClusterer(method="kmeans")
        clusterer.fit(clustering_dataset, n_clusters=3)
        path = str(tmp_path / "clu.joblib")
        clusterer.save_model(path)
        c2 = HypotheticalClusterer()
        c2.load_model(path)
        assert c2.is_trained
