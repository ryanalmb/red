import pytest

@pytest.mark.unit
def test_export_metrics():
    """Test that IntelligenceErrorMetrics is exported."""
    from cyberred.intelligence import IntelligenceErrorMetrics
    assert IntelligenceErrorMetrics is not None
