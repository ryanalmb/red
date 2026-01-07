# AsyncIO Best Practices for CyberRed

This document outlines key patterns and anti-patterns for writing robust asynchronous Python code in the CyberRed project, targeted at Python 3.11+.

## 1. Event Loop Retrieval

### 🚫 Anti-Pattern: `get_event_loop()`
Do not use `asyncio.get_event_loop()`. It is deprecated and can return closed loops or create new ones unexpectedly.

```python
# DON'T DO THIS
loop = asyncio.get_event_loop()
future = loop.create_future()
```

### ✅ Pattern: `get_running_loop()`
Use `asyncio.get_running_loop()` which guarantees you get the currently active loop. This must be called from within an async function.

```python
async def my_function():
    loop = asyncio.get_running_loop()
    future = loop.create_future()
```

## 2. Structured Concurrency (Python 3.11+)

### ✅ Pattern: `asyncio.TaskGroup`
Use `asyncio.TaskGroup` instead of `asyncio.gather()` for managing groups of tasks. It provides safer cancellation and error handling.

```python
async def main():
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(task1())
            tg.create_task(task2())
            # If any task fails, others are cancelled automatically
    except ExceptionGroup as eg:
        # Handle exceptions from multiple tasks
        pass
```

### 🚫 Anti-Pattern: Fire-and-Forget without References
Tasks created with `create_task` generally need their references kept to avoid garbage collection mid-execution, though `TaskGroup` handles this scope automatically for its children.

## 3. Task Management & Cancellation

### ✅ Pattern: Graceful Shutdown
Implement `start()` and `stop()` methods using `asyncio.Event` for control, rather than hard polling.

```python
class MyService:
    async def stop(self):
        self._shutdown_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
```

## 4. Testing Async Code

### ✅ Pattern: Async Fixtures
Use `pytest-asyncio` (v0.21+) with `asyncio_mode = "auto"`.

```python
@pytest.fixture
async def my_service():
    service = MyService()
    await service.start()
    yield service
    await service.stop()
```

### ✅ Pattern: Wait for Events
Avoid `sleep()`. Use `asyncio.wait_for()` on events.

```python
# YES
await asyncio.wait_for(service.ready_event.wait(), timeout=1.0)
```
