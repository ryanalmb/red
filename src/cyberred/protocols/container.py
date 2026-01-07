from abc import ABC, abstractmethod
from cyberred.core.models import ToolResult

class ContainerProtocol(ABC):
    @abstractmethod
    async def execute(self, code: str, timeout: int = 30) -> ToolResult:
        """Execute a command in the container."""
        pass

    @abstractmethod
    async def start(self) -> None:
        """Start the container."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the container."""
        pass

    @abstractmethod
    def is_healthy(self) -> bool:
        """Check if container is healthy."""
        pass
