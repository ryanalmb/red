# Cyber-Red Drop Box Makefile
# Cross-compilation for Windows, Linux, macOS, and Android

# Version information
VERSION ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
BUILD_TIME ?= $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")
GIT_COMMIT ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Go build settings
GO := go
MODULE := github.com/cyber-red/dropbox
BUILD_DIR := build

# Static linking flags (Task 3: AC #3)
# CGO_ENABLED=0 ensures pure Go build with no C dependencies
# -s strips symbol table, -w strips DWARF debugging info
# -extldflags '-static' ensures static linking on Linux
CGO_ENABLED := 0
LDFLAGS := -ldflags "-s -w -extldflags '-static' \
	-X $(MODULE)/internal.Version=$(VERSION) \
	-X $(MODULE)/internal.BuildTime=$(BUILD_TIME) \
	-X $(MODULE)/internal.GitCommit=$(GIT_COMMIT)"

# Build matrix (Task 2: AC #2)
# Includes both Intel and ARM architectures for modern hardware support
PLATFORMS := \
	windows/amd64 \
	linux/amd64 \
	linux/arm64 \
	darwin/amd64 \
	darwin/arm64 \
	android/arm64

# Binary naming
BINARY_NAME := dropbox

# UPX compression (optional, Task 4: AC #4)
UPX := $(shell command -v upx 2>/dev/null)

.PHONY: all build-all clean test lint help
.PHONY: build-windows build-linux build-linux-arm64 build-darwin build-darwin-arm64 build-android
.PHONY: checksums compress

# Default target
all: build-all

# Help target
help:
	@echo "Cyber-Red Drop Box Build System"
	@echo ""
	@echo "Usage:"
	@echo "  make build-all          Build for all platforms"
	@echo "  make build-windows      Build for Windows amd64"
	@echo "  make build-linux        Build for Linux amd64"
	@echo "  make build-linux-arm64  Build for Linux arm64 (AWS Graviton, RPi)"
	@echo "  make build-darwin       Build for macOS amd64 (Intel)"
	@echo "  make build-darwin-arm64 Build for macOS arm64 (Apple Silicon)"
	@echo "  make build-android      Build for Android arm64"
	@echo "  make compress       Compress binaries with UPX (if available)"
	@echo "  make checksums      Generate SHA256 checksums"
	@echo "  make test           Run tests"
	@echo "  make lint           Run linter"
	@echo "  make clean          Remove build artifacts"
	@echo ""
	@echo "Variables:"
	@echo "  VERSION=$(VERSION)"
	@echo "  BUILD_TIME=$(BUILD_TIME)"
	@echo "  GIT_COMMIT=$(GIT_COMMIT)"

# Build all platforms (Task 2: AC #2)
build-all: build-windows build-linux build-linux-arm64 build-darwin build-darwin-arm64 build-android checksums
	@echo ""
	@echo "✅ Build complete for all platforms"
	@echo ""
	@echo "Build artifacts:"
	@ls -lh $(BUILD_DIR)/*/* 2>/dev/null || true
	@echo ""
	@echo "Checksums:"
	@cat $(BUILD_DIR)/checksums.txt 2>/dev/null || true

# Windows amd64 (Task 2.4)
build-windows:
	@echo "🔨 Building for Windows amd64..."
	@mkdir -p $(BUILD_DIR)/windows
	CGO_ENABLED=$(CGO_ENABLED) GOOS=windows GOARCH=amd64 \
		$(GO) build $(LDFLAGS) -o $(BUILD_DIR)/windows/$(BINARY_NAME)-windows-amd64.exe .
	@echo "   → $(BUILD_DIR)/windows/$(BINARY_NAME)-windows-amd64.exe"

# Linux amd64 (Task 2.4)
build-linux:
	@echo "🔨 Building for Linux amd64..."
	@mkdir -p $(BUILD_DIR)/linux
	CGO_ENABLED=$(CGO_ENABLED) GOOS=linux GOARCH=amd64 \
		$(GO) build $(LDFLAGS) -o $(BUILD_DIR)/linux/$(BINARY_NAME)-linux-amd64 .
	@echo "   → $(BUILD_DIR)/linux/$(BINARY_NAME)-linux-amd64"

# Linux arm64 (Task 2.4 - ARM servers: AWS Graviton, Raspberry Pi, etc.)
build-linux-arm64:
	@echo "🔨 Building for Linux arm64..."
	@mkdir -p $(BUILD_DIR)/linux
	CGO_ENABLED=$(CGO_ENABLED) GOOS=linux GOARCH=arm64 \
		$(GO) build $(LDFLAGS) -o $(BUILD_DIR)/linux/$(BINARY_NAME)-linux-arm64 .
	@echo "   → $(BUILD_DIR)/linux/$(BINARY_NAME)-linux-arm64"

# macOS amd64 (Task 2.4 - Intel Macs)
build-darwin:
	@echo "🔨 Building for macOS amd64..."
	@mkdir -p $(BUILD_DIR)/darwin
	CGO_ENABLED=$(CGO_ENABLED) GOOS=darwin GOARCH=amd64 \
		$(GO) build $(LDFLAGS) -o $(BUILD_DIR)/darwin/$(BINARY_NAME)-darwin-amd64 .
	@echo "   → $(BUILD_DIR)/darwin/$(BINARY_NAME)-darwin-amd64"

# macOS arm64 (Task 2.4 - Apple Silicon: M1/M2/M3)
build-darwin-arm64:
	@echo "🔨 Building for macOS arm64 (Apple Silicon)..."
	@mkdir -p $(BUILD_DIR)/darwin
	CGO_ENABLED=$(CGO_ENABLED) GOOS=darwin GOARCH=arm64 \
		$(GO) build $(LDFLAGS) -o $(BUILD_DIR)/darwin/$(BINARY_NAME)-darwin-arm64 .
	@echo "   → $(BUILD_DIR)/darwin/$(BINARY_NAME)-darwin-arm64"

# Android arm64 (Task 2.4)
# Note: Android builds may require Android NDK for some features
build-android:
	@echo "🔨 Building for Android arm64..."
	@mkdir -p $(BUILD_DIR)/android
	CGO_ENABLED=$(CGO_ENABLED) GOOS=android GOARCH=arm64 \
		$(GO) build $(LDFLAGS) -o $(BUILD_DIR)/android/$(BINARY_NAME)-android-arm64 .
	@echo "   → $(BUILD_DIR)/android/$(BINARY_NAME)-android-arm64"

# Generate checksums (Task 4.4)
checksums:
	@echo "📝 Generating checksums..."
	@mkdir -p $(BUILD_DIR)
	@rm -f $(BUILD_DIR)/checksums.txt
	@find $(BUILD_DIR) -type f \( -name "$(BINARY_NAME)-*" \) -exec sha256sum {} \; 2>/dev/null | \
		sed 's|$(BUILD_DIR)/||' > $(BUILD_DIR)/checksums.txt || \
		find $(BUILD_DIR) -type f \( -name "$(BINARY_NAME)-*" \) -exec shasum -a 256 {} \; 2>/dev/null | \
		sed 's|$(BUILD_DIR)/||' > $(BUILD_DIR)/checksums.txt
	@echo "   → $(BUILD_DIR)/checksums.txt"

# Compress binaries with UPX (Task 4.2 - optional)
compress:
ifdef UPX
	@echo "📦 Compressing binaries with UPX..."
	@for binary in $(BUILD_DIR)/*/*; do \
		if [ -f "$$binary" ] && [ "$${binary##*.}" != "txt" ]; then \
			echo "   Compressing $$binary..."; \
			$(UPX) --best --lzma "$$binary" 2>/dev/null || echo "   ⚠️  UPX failed for $$binary (may not support this format)"; \
		fi \
	done
	@echo "✅ Compression complete"
else
	@echo "⚠️  UPX not found - skipping compression"
	@echo "   Install UPX for smaller binaries: https://upx.github.io/"
endif

# Run tests
test:
	@echo "🧪 Running tests..."
	$(GO) test -v -race -cover ./...

# Run linter
lint:
	@echo "🔍 Running linter..."
	@command -v golangci-lint >/dev/null 2>&1 && golangci-lint run || \
		echo "⚠️  golangci-lint not found - skipping lint"

# Clean build artifacts (Task 2.5)
clean:
	@echo "🧹 Cleaning build artifacts..."
	@rm -rf $(BUILD_DIR)
	@echo "✅ Clean complete"

# Verify static linking (Task 3.3)
verify-static: build-linux
	@echo "🔍 Verifying static linking..."
	@if command -v ldd >/dev/null 2>&1; then \
		echo "Checking with ldd:"; \
		ldd $(BUILD_DIR)/linux/$(BINARY_NAME)-linux-amd64 2>&1 || echo "   ✅ Binary is statically linked (not a dynamic executable)"; \
	else \
		echo "⚠️  ldd not available - skipping verification"; \
	fi

# Show binary sizes
sizes: build-all
	@echo ""
	@echo "📊 Binary sizes:"
	@echo "─────────────────────────────────────────"
	@find $(BUILD_DIR) -type f \( -name "$(BINARY_NAME)-*" \) -exec ls -lh {} \; 2>/dev/null | \
		awk '{print $$5 "\t" $$9}' | sed 's|$(BUILD_DIR)/||'
