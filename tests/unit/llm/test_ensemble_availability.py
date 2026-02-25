from cyberred.llm.ensemble import DirectorEnsemble, DirectorRole


def test_availability_snapshot_lists_all_roles() -> None:
    ensemble = DirectorEnsemble()

    snapshot = ensemble.get_availability_snapshot()

    assert snapshot["available_count"] == len(DirectorRole)
    assert set(snapshot["available_roles"]) == {role.value for role in DirectorRole}
    for role in DirectorRole:
        role_state = snapshot["roles"][role.value]
        assert role_state["state"] == "available"
        assert role_state["failure_count"] == 0
        assert role_state["excluded_until"] is None


def test_reset_role_circuit_breaker_reopens_excluded_role() -> None:
    ensemble = DirectorEnsemble()
    threshold = ensemble._circuit_breaker._failure_threshold
    for _ in range(threshold):
        ensemble._circuit_breaker.record_failure(DirectorRole.STRATEGIST)

    excluded_snapshot = ensemble.get_availability_snapshot()
    assert "strategist" not in excluded_snapshot["available_roles"]
    assert excluded_snapshot["roles"]["strategist"]["state"] == "excluded"

    ensemble.reset_role_circuit_breaker(DirectorRole.STRATEGIST)
    recovered_snapshot = ensemble.get_availability_snapshot()

    assert "strategist" in recovered_snapshot["available_roles"]
    assert recovered_snapshot["roles"]["strategist"]["state"] == "available"
    assert recovered_snapshot["roles"]["strategist"]["failure_count"] == 0
    assert recovered_snapshot["roles"]["strategist"]["excluded_until"] is None
