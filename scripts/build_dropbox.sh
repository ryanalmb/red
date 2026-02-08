#!/usr/bin/env bash
# Cyber-Red Drop Box Build Script
# Story 12.5: Drop Box Go Module Structure
#
# This script orchestrates the full build pipeline for the drop box binary.
# It checks prerequisites, builds for all platforms, and provides a summary.

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DROPBOX_DIR="$PROJECT_ROOT/dropbox"

# Minimum Go version required (Task 6.2)
MIN_GO_VERSION="1.21"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Go is installed and meets minimum version (Task 6.2)
check_go_version() {
    log_info "Checking Go version..."
    
    if ! command -v go &> /dev/null; then
        log_error "Go is not installed. Please install Go ${MIN_GO_VERSION}+ from https://golang.org/dl/"
        exit 1
    fi
    
    GO_VERSION=$(go version | awk '{print $3}' | sed 's/go//')
    GO_MAJOR=$(echo "$GO_VERSION" | cut -d. -f1)
    GO_MINOR=$(echo "$GO_VERSION" | cut -d. -f2)
    
    MIN_MAJOR=$(echo "$MIN_GO_VERSION" | cut -d. -f1)
    MIN_MINOR=$(echo "$MIN_GO_VERSION" | cut -d. -f2)
    
    if [[ "$GO_MAJOR" -lt "$MIN_MAJOR" ]] || [[ "$GO_MAJOR" -eq "$MIN_MAJOR" && "$GO_MINOR" -lt "$MIN_MINOR" ]]; then
        log_error "Go version $GO_VERSION is below minimum required version $MIN_GO_VERSION"
        log_error "Please upgrade Go from https://golang.org/dl/"
        exit 1
    fi
    
    log_success "Go version $GO_VERSION meets minimum requirement ($MIN_GO_VERSION)"
}

# Check for Android NDK (Task 6.3)
check_android_ndk() {
    log_info "Checking Android NDK for android/arm64 builds..."
    
    if [[ -n "${ANDROID_NDK_HOME:-}" ]] && [[ -d "$ANDROID_NDK_HOME" ]]; then
        log_success "Android NDK found at: $ANDROID_NDK_HOME"
        return 0
    fi
    
    if [[ -n "${ANDROID_HOME:-}" ]] && [[ -d "$ANDROID_HOME/ndk" ]]; then
        # Find latest NDK version
        NDK_DIR=$(find "$ANDROID_HOME/ndk" -maxdepth 1 -type d | sort -V | tail -1)
        if [[ -d "$NDK_DIR" ]]; then
            export ANDROID_NDK_HOME="$NDK_DIR"
            log_success "Android NDK found at: $ANDROID_NDK_HOME"
            return 0
        fi
    fi
    
    log_warn "Android NDK not found. Android builds will use pure Go (no CGO)."
    log_warn "Set ANDROID_NDK_HOME or install NDK via Android Studio for full Android support."
    return 0
}

# Check for optional tools
check_optional_tools() {
    log_info "Checking optional tools..."
    
    if command -v upx &> /dev/null; then
        log_success "UPX found - binaries will be compressed"
    else
        log_warn "UPX not found - binaries will not be compressed"
        log_warn "Install UPX for smaller binaries: https://upx.github.io/"
    fi
}

# Build all platforms
build_all() {
    log_info "Building drop box for all platforms..."
    echo ""
    
    cd "$DROPBOX_DIR"
    
    # Run make build-all
    if make build-all; then
        log_success "Build completed successfully!"
    else
        log_error "Build failed!"
        exit 1
    fi
}

# Compress binaries (optional)
compress_binaries() {
    if command -v upx &> /dev/null; then
        log_info "Compressing binaries with UPX..."
        cd "$DROPBOX_DIR"
        make compress || log_warn "Some binaries could not be compressed"
    fi
}

# Show build summary (Task 6.4)
show_summary() {
    echo ""
    echo "=============================================="
    echo "       Cyber-Red Drop Box Build Summary       "
    echo "=============================================="
    echo ""
    
    BUILD_DIR="$DROPBOX_DIR/build"
    
    if [[ -d "$BUILD_DIR" ]]; then
        log_info "Build artifacts:"
        echo ""
        
        # Show file sizes for each platform
        for platform_dir in "$BUILD_DIR"/*; do
            if [[ -d "$platform_dir" ]]; then
                platform=$(basename "$platform_dir")
                echo "  📦 $platform:"
                for binary in "$platform_dir"/*; do
                    if [[ -f "$binary" ]] && [[ "$(basename "$binary")" != "checksums.txt" ]]; then
                        size=$(ls -lh "$binary" | awk '{print $5}')
                        name=$(basename "$binary")
                        echo "     - $name ($size)"
                    fi
                done
            fi
        done
        
        echo ""
        
        # Show checksums
        if [[ -f "$BUILD_DIR/checksums.txt" ]]; then
            log_info "Checksums (SHA256):"
            echo ""
            cat "$BUILD_DIR/checksums.txt" | sed 's/^/     /'
        fi
        
        echo ""
        log_success "All binaries built successfully!"
        echo ""
        echo "  Output directory: $BUILD_DIR"
        echo ""
    else
        log_error "Build directory not found: $BUILD_DIR"
        exit 1
    fi
}

# Main execution
main() {
    echo ""
    echo "=============================================="
    echo "       Cyber-Red Drop Box Build Script        "
    echo "=============================================="
    echo ""
    
    # Change to project root
    cd "$PROJECT_ROOT"
    
    # Check prerequisites
    check_go_version
    check_android_ndk
    check_optional_tools
    
    echo ""
    
    # Build
    build_all
    
    # Compress (optional)
    compress_binaries
    
    # Summary
    show_summary
}

# Run main function
main "$@"
