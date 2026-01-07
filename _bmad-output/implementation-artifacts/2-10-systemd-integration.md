# Story 2.10: systemd Integration

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want **systemd service for daemon auto-start**,
So that **Cyber-Red starts on boot and restarts on failure**.

## Acceptance Criteria

1. **Given** Cyber-Red is installed on a systemd Linux system
2. **When** I run `systemctl enable cyber-red`
3. **Then** daemon starts automatically on boot
4. **And** daemon restarts automatically on failure
5. **And** `systemctl status cyber-red` shows daemon state
6. **And** `journalctl -u cyber-red` shows daemon logs
7. **And** service runs as dedicated `cyberred` user (not root)
8. **And** unit tests verify service file generation
9. **And** integration tests verify service installation/uninstallation

## Tasks / Subtasks

> [!IMPORTANT]
> **GOAL: Production-ready systemd integration.** The operator should be able to install Cyber-Red as a managed system service that survives reboots, restarts on failure, and logs to journald. This story provides the infrastructure for enterprise deployment.

> [!WARNING]
> **EXISTING DAEMON INFRASTRUCTURE:** `daemon/server.py` already supports `--foreground` mode. The CLI command `daemon start --foreground` is designed for systemd `Type=simple`. This story adds the service file and installation commands.

### Phase 1: Service File Generation

- [x] Task 1: Create Service File Template (AC: #1, #3, #4, #5, #6, #7)
  - [x] Create `src/cyberred/daemon/systemd.py` module
  - [x] Define `SERVICE_TEMPLATE` constant with unit file contents (per architecture lines 471-485)
  - [x] Include `[Unit]` section: Description, After=network.target redis.service
  - [x] Include `[Service]` section: Type=simple, ExecStart, ExecStop, Restart=on-failure, User=cyberred
  - [x] Include `[Install]` section: WantedBy=multi-user.target
  - [x] Add `StandardOutput=journal` and `StandardError=journal` for journald integration
  - [x] Make ExecStart path configurable (auto-detect from `sys.executable` or `/usr/local/bin/cyber-red`)
  - [x] Add `RestartSec=5` for restart delay
  - [x] Add `Environment="PYTHONUNBUFFERED=1"` for real-time logging
  - [x] Verification: Unit tests for template string correctness

- [x] Task 2: Implement `generate_service_file()` Function (AC: #1)
  - [x] Function signature: `def generate_service_file(user: str = "cyberred", exec_path: Optional[Path] = None) -> str`
  - [x] Auto-detect executable path if not provided
  - [x] Format template with configurable values
  - [x] Verification: Unit test with custom user and path

- [x] Task 3: Implement `write_service_file()` Function (AC: #1)
  - [x] Function signature: `def write_service_file(content: str, service_path: Path = Path("/etc/systemd/system/cyber-red.service")) -> None`
  - [x] Write service file atomically (write to temp, then rename)
  - [x] Set correct permissions (644, root:root)
  - [x] Raise `PermissionError` if not root
  - [x] Verification: Unit test with mocked file operations

### Phase 2: CLI Integration

- [x] Task 4: Add `daemon install` Command (AC: #1, #2)
  - [x] Add `install` subcommand to `daemon_app` in `cli.py`
  - [x] Options: `--user` (default: cyberred), `--no-enable` (skip systemctl enable)
  - [x] Check if running as root, exit with error if not
  - [x] Generate and write service file to `/etc/systemd/system/cyber-red.service`
  - [x] Run `systemctl daemon-reload`
  - [x] Run `systemctl enable cyber-red` (unless --no-enable)
  - [x] Print success message with next-steps instructions
  - [x] Verification: Unit test with subprocess mocks

- [x] Task 5: Add `daemon uninstall` Command (AC: #9)
  - [x] Add `uninstall` subcommand to `daemon_app` in `cli.py`
  - [x] Check if running as root, exit with error if not
  - [x] Stop service if running: `systemctl stop cyber-red`
  - [x] Disable service: `systemctl disable cyber-red`
  - [x] Remove service file from `/etc/systemd/system/cyber-red.service`
  - [x] Run `systemctl daemon-reload`
  - [x] Print uninstall confirmation
  - [x] Verification: Unit test with subprocess mocks

- [x] Task 6: Add `daemon logs` Command (AC: #6)
  - [x] Add `logs` subcommand to `daemon_app` in `cli.py`
  - [x] Options: `--follow/-f` (tail logs), `--lines/-n` (number of lines, default 50)
  - [x] Execute `journalctl -u cyber-red` with appropriate flags
  - [x] Verification: Unit test verifies correct journalctl invocation

### Phase 3: User Creation Helper

- [x] Task 7: Create `create_service_user()` Function (AC: #7)
  - [x] Function signature: `def create_service_user(username: str = "cyberred") -> bool`
  - [x] Check if user exists: `id <username>`
  - [x] If not exists, create: `useradd --system --shell /sbin/nologin --home-dir /var/lib/cyber-red <username>`
  - [x] Create home directory with correct ownership
  - [x] Return True if created, False if already exists
  - [x] Raise `PermissionError` if not root
  - [x] Verification: Unit test with subprocess mocks

- [x] Task 8: Integrate User Creation into `daemon install` (AC: #7)
  - [x] Prompt user to create service user if it doesn't exist
  - [x] Add `--create-user` flag to auto-create without prompt
  - [x] Ensure storage base_path (`~/.cyber-red/` or configured path) exists with correct ownership
  - [x] Create storage directory: `mkdir -p <base_path> && chown <user>:<user> <base_path>`
  - [x] Log user creation result
  - [x] Verification: Unit test install flow with user creation and directory setup

### Phase 4: Daemon Foreground Enhancements

- [x] Task 9: Enhance Signal Handling for systemd (AC: #3, #4)
  - [x] **NOTE:** SIGTERM/SIGINT already handled in `server.py` (lines 517-522) — verify behavior only
  - [x] Add SIGHUP handler for future config reload support (new functionality)
  - [x] Ensure clean exit on SIGTERM (exit code 0 for "success", non-zero for "failure") — verify existing
  - [x] Add log message specifying which signal was received (currently just "shutdown_signal_received")
  - [x] Verification: Unit test SIGHUP handling (SIGTERM/SIGINT already tested)

- [x] Task 10: Add Structured Logging for journald (AC: #6)
  - [x] **NOTE:** `cli.py` (lines 33-40) already configures structlog — reuse pattern
  - [x] Ensure structlog JSON output is compatible with journald
  - [ ] Add `--log-format` option to `daemon start`: `json`, `console` (default in foreground: console) — *deferred to future story*
  - [ ] When running under systemd, auto-detect via `JOURNAL_STREAM` env var (optional enhancement) — *deferred*
  - [x] Verification: Manual test with `journalctl -u cyber-red -o json`

### Phase 5: Testing

- [x] Task 11: Unit Tests for systemd Module (AC: #8)
  - [x] Create `tests/unit/daemon/test_systemd.py`
  - [x] Test: `test_generate_service_file_default` — default template values
  - [x] Test: `test_generate_service_file_custom_user` — custom user name
  - [x] Test: `test_generate_service_file_custom_exec_path` — custom executable path
  - [x] Test: `test_create_service_user_new_user` — user creation subprocess
  - [x] Test: `test_create_service_user_already_exists` — returns False
  - [x] Test: `test_create_service_user_permission_error` — not root
  - [x] Verification: `pytest tests/unit/daemon/test_systemd.py -v`

- [x] Task 12: Unit Tests for CLI Commands (AC: #8)
  - [x] Add to `tests/unit/test_cli.py` or create dedicated file
  - [x] Test: `test_daemon_install_not_root` — error when not root
  - [x] Test: `test_daemon_install_success` — mocked subprocess calls
  - [x] Test: `test_daemon_uninstall_not_root` — error when not root
  - [x] Test: `test_daemon_uninstall_success` — mocked subprocess calls
  - [x] Test: `test_daemon_logs_default` — correct journalctl command
  - [x] Test: `test_daemon_logs_follow` — includes -f flag
  - [x] Verification: `pytest tests/unit/test_cli.py -v -k systemd`

- [x] Task 13: Integration Tests for Service Lifecycle (AC: #9)
  - [x] Create `tests/integration/daemon/test_systemd_integration.py`
  - [x] **SKIP CONDITIONS**: Tests only run on systemd hosts (`pytest.mark.skipif`)
  - [x] Test: `test_service_file_installation_uninstallation` (requires root, mark with `@pytest.mark.requires_root`)
  - [x] Test creates temp service file, installs, verifies `systemctl status`, uninstalls, verifies removal
  - [x] Clean up service file after test
  - [x] Verification: `sudo pytest tests/integration/daemon/test_systemd_integration.py -v` (on systemd host)

### Phase 6: Coverage Gate

- [x] Task 14: Achieve 100% Test Coverage (AC: #8, #9)
  - [x] `daemon/systemd.py`: 100% coverage (38 tests)
  - [x] All new CLI commands: covered via 8 new tests in `test_cli.py`
  - [x] Verification: `pytest --cov=cyberred.daemon.systemd --cov-fail-under=100` ✅

## Dev Notes

### Architecture Context

Per architecture document (lines 469-485), the systemd service file should be:

```ini
# /etc/systemd/system/cyber-red.service
[Unit]
Description=Cyber-Red Daemon
After=network.target redis.service

[Service]
Type=simple
ExecStart=/usr/local/bin/cyber-red daemon start --foreground
ExecStop=/usr/local/bin/cyber-red daemon stop
Restart=on-failure
RestartSec=5
User=cyberred
Environment="PYTHONUNBUFFERED=1"
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### Key Design Decisions

1. **Type=simple**: Daemon runs in foreground (`--foreground` flag), systemd manages lifecycle directly.
2. **Restart=on-failure**: Automatic restart only on non-zero exit.
3. **RestartSec=5**: Wait 5 seconds before restart to avoid rapid restart loops.
4. **User=cyberred**: Dedicated non-root user for security.
5. **After=redis.service**: Start after Redis if Redis is managed by systemd.
6. **StandardOutput/StandardError=journal**: Direct logs to journald.

### CLI Command Reference

```bash
# Install service (requires root)
sudo cyber-red daemon install                  # Default: user=cyberred
sudo cyber-red daemon install --user myuser    # Custom user
sudo cyber-red daemon install --no-enable      # Don't auto-enable
sudo cyber-red daemon install --create-user    # Auto-create user

# Uninstall service (requires root)
sudo cyber-red daemon uninstall

# View logs
cyber-red daemon logs                          # Last 50 lines
cyber-red daemon logs -n 100                   # Last 100 lines
cyber-red daemon logs -f                       # Follow logs
```

### References

- [Source: architecture.md#systemd-integration (lines 469-485)](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L469-L485)
- [Source: epics-stories.md#Story 2.10 (lines 1309-1329)](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L1309-L1329)

## Dev Agent Record

### Agent Model Used

Claude 3.5 Sonnet (Anthropic)

### Debug Log References

### Completion Notes List

- Created `src/cyberred/daemon/systemd.py` with SERVICE_TEMPLATE, generate_service_file(), write_service_file(), create_service_user(), ensure_storage_directory(), and systemctl helper functions
- Added CLI commands `daemon install`, `daemon uninstall`, `daemon logs` to `src/cyberred/cli.py`
- Enhanced signal handling in `server.py` with SIGHUP handler and improved logging to show signal name
- Created 37 unit tests in `tests/unit/daemon/test_systemd.py` covering all systemd module functions
- Added 8 CLI tests in `tests/unit/test_cli.py` for new daemon commands
- Task 10 partial: `--log-format` option deferred to future story for scope control
- Task 13 implemented: integration tests created in `tests/integration/daemon/test_systemd_integration.py` with proper skip logic for non-root environments
- **Security Fix:** Added strict boolean validation for `user` parameter in `generate_service_file` to prevent injection attacks (found in adversarial review)
- Achieved 100% coverage on `daemon/systemd.py` including new security validation logic

### File List

**Created:**
- `src/cyberred/daemon/systemd.py` — systemd integration module (317 lines)
- `tests/unit/daemon/test_systemd.py` — systemd unit tests (450 lines)
- `tests/integration/daemon/test_systemd_integration.py` — systemd integration tests (67 lines)

**Modified:**
- `src/cyberred/cli.py` — added daemon install/uninstall/logs commands (183 lines added)
- `src/cyberred/daemon/server.py` — enhanced signal handling with SIGHUP (10 lines changed)
- `tests/unit/test_cli.py` — added TestDaemonSystemdCommands class (139 lines added)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — story status: review → done

