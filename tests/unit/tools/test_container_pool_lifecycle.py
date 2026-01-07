import pytest
from cyberred.tools import ContainerPool, MockContainer

@pytest.mark.unit
@pytest.mark.asyncio
async def test_container_pool_lifecycle_flow():
    """Verify full lifecycle: init -> acquire -> execute -> release."""
    # 1. Init
    pool = ContainerPool(mode="mock", size=2)
    
    # 2. Acquire
    async with pool.acquire() as container:
        assert isinstance(container, MockContainer)
        
        # 3. Execute
        result = await container.execute("nmap target")
        assert result.success
        assert "Starting Nmap" in result.stdout
        
    # 4. Release (handled by context manager)
    # Verify pool state? Mock implementation simplistic, but we can verify we can re-acquire
    
    # Re-acquire to prove release worked (if pool size was small)
    async with pool.acquire() as container2:
        assert isinstance(container2, MockContainer)
