# Cyber-Red Drop Box

A lightweight, cross-platform agent for Cyber-Red penetration testing engagements.

## Overview

The drop box binary connects to the C2 server via mTLS WebSocket and executes commands on target systems. It supports WiFi toolkit operations for wireless assessments.

## Prerequisites

- **Go 1.21+** - [Download](https://golang.org/dl/)
- **Make** - For build automation
- **UPX** (optional) - For binary compression

## Quick Start

```bash
# Build for all platforms
make build-all

# Build for specific platform
make build-linux
make build-darwin-arm64
make build-windows

# Run tests
make test

# Clean build artifacts
make clean
```

## Build Matrix

| Platform | Architecture | Binary Name |
|----------|--------------|-------------|
| Windows | amd64 | `dropbox-windows-amd64.exe` |
| Linux | amd64 | `dropbox-linux-amd64` |
| Linux | arm64 | `dropbox-linux-arm64` |
| macOS | amd64 (Intel) | `dropbox-darwin-amd64` |
| macOS | arm64 (Apple Silicon) | `dropbox-darwin-arm64` |
| Android | arm64 | `dropbox-android-arm64` |

## Project Structure

```
dropbox/
├── main.go              # Entry point with CLI handling
├── go.mod               # Module definition (zero dependencies)
├── Makefile             # Cross-compilation targets
├── c2/                  # mTLS WebSocket client (Story 12.6)
│   ├── client.go        # C2 connection client
│   └── config.go        # Connection configuration
├── wifi/                # WiFi toolkit wrapper (Story 12.7)
│   ├── toolkit.go       # Tool wrapper interface
│   └── commands.go      # Command definitions
├── internal/            # Shared utilities
│   ├── version.go       # Version info (injected at build)
│   └── logger.go        # Structured logging
└── build/               # Output directory (gitignored)
```

## Usage

```bash
# Show version
./dropbox-linux-amd64 --version

# Show help
./dropbox-linux-amd64 --help

# Connect to C2 server (requires config)
./dropbox-linux-amd64 --config /path/to/config.yaml
```

## Security Features

- **Zero dependencies** - Pure Go for maximum portability
- **Static linking** - No external library dependencies
- **mTLS** - Mutual TLS authentication with certificate pinning
- **Stripped binaries** - Debug symbols removed for operational security

## Related Stories

- **Story 12.1**: mTLS C2 Server
- **Story 12.2**: C2 Message Protocol
- **Story 12.3**: Certificate Manager
- **Story 12.4**: Heartbeat Monitoring
- **Story 12.5**: Drop Box Go Module Structure (this module)
- **Story 12.6**: Drop Box mTLS Client (implements c2/ package)
- **Story 12.7**: WiFi Toolkit Wrapper (implements wifi/ package)

## Development

```bash
# Run tests with coverage
go test -v -race -cover ./...

# Run linter (requires golangci-lint)
make lint

# Verify static linking
make verify-static
```

## License

Proprietary - Cyber-Red Project
