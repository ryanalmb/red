# Kali Linux Testcontainers Patterns

This document outlines patterns for using Kali Linux containers in integration tests and production, ensuring compliance with the "NO MOCKS" policy and FR31/FR35.

## 1. Environment Profiles (CI vs. Production)

We use two different container strategies depending on the environment.

### Profile A: "CI/Dev" (Lightweight)
*   **Goal:** Fast feedback, low disk usage.
*   **Image:** Custom minimal image (`Dockerfile.kali-dev`).
*   **Tools:** Top ~30 most frequent tools (nmap, sqlmap, nuclei, etc.).
*   **Size:** ~2-3GB uncompressed.
*   **Use Case:** Local unit tests, GitHub Actions integration tests.

### Profile B: "Production" (Heavy)
*   **Goal:** Maximum capability (FR31: 600+ tools).
*   **Image:** `kalilinux/kali-linux-large` or `kali-linux-everything`.
*   **Tools:** 600+ tools pre-installed.
*   **Size:** ~20-35GB uncompressed.
*   **Use Case:** Live engagements, E2E cyber range validation.

## 2. Resource Constraints (RAM vs. Disk)

It is a common misconception that larger images consume more RAM.

*   **RAM:** Runtime memory usage is determined by **running processes**, not image size. An idle 35GB "Everything" container consumes roughly the same RAM (<100MB) as a 100MB Alpine container.
*   **Disk:** The primary cost is disk storage. Production nodes must have sufficient storage (50GB+) to pull the `kali-linux-everything` image.
*   **Startup Time:** Container startup time is negligible for both profiles once the image is pulled.

## 3. Implementation Pattern

Use `wrapper` logic to select the image based on config.

```python
import os
from testcontainers.core.container import DockerContainer

def get_kali_image():
    env = os.getenv("CYBER_RED_ENV", "dev")
    if env == "prod":
        return "kalilinux/kali-linux-everything"
    else:
        # Assumes local build or registry pull of dev image
        return "cyber-red/kali-dev:latest"

@pytest.fixture
def kali_container():
    container = DockerContainer(get_kali_image())
    container.start()
    yield container
    container.stop()
```

## 4. Basic Tool Execution

Use `container.exec()` to run tools.

```python
def test_nmap_scan(kali_container):
    code, output = kali_container.exec(["nmap", "--version"])
    assert code == 0
```
