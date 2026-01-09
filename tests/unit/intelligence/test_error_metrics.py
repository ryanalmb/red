import pytest
from cyberred.intelligence.metrics import IntelligenceErrorMetrics

@pytest.mark.unit
class TestIntelligenceErrorMetrics:
    def test_instantiation(self):
        """Test that metrics class can be instantiated."""
        metrics = IntelligenceErrorMetrics()
        assert metrics is not None

    def test_record_timeout(self):
        """Test recording a timeout."""
        metrics = IntelligenceErrorMetrics()
        metrics.record_timeout("source_a")
        
        data = metrics.get_metrics()
        assert data["timeouts"]["source_a"] == 1
        assert data["total_timeouts"] == 1

        metrics.record_timeout("source_a")
        data = metrics.get_metrics()
        assert data["timeouts"]["source_a"] == 2
        assert data["total_timeouts"] == 2

    def test_record_error(self):
        """Test recording an error."""
        metrics = IntelligenceErrorMetrics()
        metrics.record_error("source_b", "ConnectionError")
        
        data = metrics.get_metrics()
        assert data["errors"]["source_b"]["ConnectionError"] == 1
        assert data["total_errors"] == 1

        metrics.record_error("source_b", "ConnectionError")
        metrics.record_error("source_b", "ValueError")
        
        data = metrics.get_metrics()
        assert data["errors"]["source_b"]["ConnectionError"] == 2
        assert data["errors"]["source_b"]["ValueError"] == 1
        assert data["total_errors"] == 3

    def test_get_metrics_structure(self):
        """Test structure of get_metrics output."""
        metrics = IntelligenceErrorMetrics()
        metrics.record_timeout("s1")
        metrics.record_error("s1", "Err")
        
        data = metrics.get_metrics()
        assert "timeouts" in data
        assert "errors" in data
        assert "total_timeouts" in data
        assert "total_errors" in data
        assert isinstance(data["timeouts"], dict)
        assert isinstance(data["errors"], dict)

    def test_get_source_metrics(self):
        """Test retrieving metrics for specific source."""
        metrics = IntelligenceErrorMetrics()
        metrics.record_timeout("s1")
        metrics.record_error("s1", "E1")
        metrics.record_timeout("s2")
        
        s1_data = metrics.get_source_metrics("s1")
        assert s1_data["timeouts"] == 1
        assert s1_data["errors"]["E1"] == 1
        
        s2_data = metrics.get_source_metrics("s2")
        assert s2_data["timeouts"] == 1
        assert s2_data["errors"] == {}
        
        empty_data = metrics.get_source_metrics("s3")
        assert empty_data["timeouts"] == 0
        assert empty_data["errors"] == {}

    def test_reset(self):
        """Test resetting metrics."""
        metrics = IntelligenceErrorMetrics()
        metrics.record_timeout("s1")
        metrics.record_error("s1", "E1")
        
        metrics.reset()
        
        data = metrics.get_metrics()
        assert data["total_timeouts"] == 0
        assert data["total_errors"] == 0
        assert data["timeouts"] == {}
        assert data["errors"] == {}
