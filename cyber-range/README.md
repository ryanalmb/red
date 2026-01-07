# Cyber Range Test Environment

Standardized vulnerable target environment for Cyber-Red E2E and emergence testing.

## Quick Start

```bash
# Start all vulnerable services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| DVWA | 8080 | Damn Vulnerable Web Application |
| SSH | 2222 | Weak credential SSH server |
| SMB | 445 | SMBv1 enabled Samba server |
| FTP | 21 | Anonymous access FTP server |

## Test Credentials

### DVWA
- Default: `admin` / `password`
- Security Level: Low (for testing)

### SSH
- `testuser` / `password123`

### SMB
- Guest: `guest` / `guest`
- Admin: `admin` / `weakpass`

### FTP
- Anonymous: `anonymous` / `anonymous`
- User: `ftpuser` / `ftppass`

## Network

All services are isolated on `cyber-range-net` (172.28.0.0/16).

## Files

- `docker-compose.yml` - Service definitions
- `expected-findings.json` - Known vulnerabilities for test validation
- `emergence-baseline.json` - Baseline for emergence score calculation
- `targets/` - Service-specific configurations (placeholder structure)

## Usage in Tests

```python
# Example: conftest.py fixture
import pytest
import subprocess

@pytest.fixture(scope="session")
def cyber_range():
    """Start cyber-range environment for E2E tests."""
    subprocess.run(
        ["docker-compose", "-f", "cyber-range/docker-compose.yml", "up", "-d"],
        check=True
    )
    yield
    subprocess.run(
        ["docker-compose", "-f", "cyber-range/docker-compose.yml", "down"],
        check=True
    )
```

## Emergence Testing

See `emergence-baseline.json` for:
- Expected isolated agent paths
- Expected stigmergic novel paths
- NFR35-37 validation requirements
