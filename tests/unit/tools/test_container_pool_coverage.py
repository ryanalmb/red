import pytest
from cyberred.tools.container_pool import ContainerPool, MockContainer

@pytest.mark.asyncio
async def test_real_mode_raises_error():
    """Test that real mode raises NotImplementedError."""
    pool = ContainerPool(mode="real")
    with pytest.raises(NotImplementedError):
        await pool.acquire()

@pytest.mark.asyncio
async def test_release_when_queue_full():
    """Test releasing to a full pool does not block or overflow."""
    pool = ContainerPool(mode="mock", size=1)
    # Fill manually or via release
    c1 = MockContainer()
    c2 = MockContainer()
    
    # Fill the slot
    await pool.release(c1)
    assert pool._available.qsize() == 1
    
    # Try to release another
    await pool.release(c2)
    # Should still be 1 (dropped)
    assert pool._available.qsize() == 1

@pytest.mark.asyncio
async def test_fixture_loader_caching():
    """Test that fixture loader caches content."""
    from cyberred.tools.container_pool import FixtureLoader
    loader = FixtureLoader()
    # First load
    content1 = loader.load("nmap.txt")
    # Second load (hit cache)
    content2 = loader.load("nmap.txt")
    assert content1 == content2

@pytest.mark.asyncio
async def test_mock_container_methods():
    """Test pass-through methods of MockContainer."""
    c = MockContainer()
    await c.start()
    await c.stop()
    assert c.is_healthy() is True

@pytest.mark.asyncio
async def test_execute_edge_cases():
    """Test execute with empty or invalid commands."""
    c = MockContainer()
    
    # Empty string
    res = await c.execute("")
    assert not res.success
    assert "Could not detect tool" in res.stderr
    
    # Whitespace only
    res = await c.execute("   ")
    assert not res.success
    
    # None (type ignore since signature expects str)
    res = await c.execute(None) # type: ignore
    assert not res.success

@pytest.mark.asyncio
async def test_real_mode_release():
    """Test that releasing in real mode does nothing (no-op)."""
    pool = ContainerPool(mode="real")
    c = MockContainer()
    # Should not raise
    await pool.release(c)
    # Queue should remain empty (since init empty and no put)
    assert pool._available.empty()

@pytest.mark.asyncio
async def test_execute_unknown_tool():
    """Test execute with unknown tool."""
    c = MockContainer()
    res = await c.execute("unknown_tool_xyz")
    # Should use fallback message
    assert res.success
    assert "Mock output (fixture not found)" in res.stdout

@pytest.mark.asyncio
async def test_context_manager_edge_case():
    """Test __aexit__ when no container was acquired."""
    pool = ContainerPool(mode="mock")
    ctx = pool.acquire()
    # Manually call aexit without aenter having run (container is None)
    await ctx.__aexit__(None, None, None)
    # Should just return without error
