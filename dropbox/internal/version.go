// Package internal provides shared utilities for the drop box binary.
package internal

// Version information injected at build time via ldflags.
// Example: -ldflags "-X github.com/cyber-red/dropbox/internal.Version=1.0.0"
var (
	// Version is the semantic version of the drop box binary.
	Version = "dev"

	// BuildTime is the timestamp when the binary was built.
	BuildTime = "unknown"

	// GitCommit is the git commit hash at build time.
	GitCommit = "unknown"
)
