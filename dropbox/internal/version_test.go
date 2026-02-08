package internal

import (
	"testing"
)

func TestVersionDefaults(t *testing.T) {
	// Test that default values are set
	if Version == "" {
		t.Error("Version should not be empty")
	}
	if BuildTime == "" {
		t.Error("BuildTime should not be empty")
	}
	if GitCommit == "" {
		t.Error("GitCommit should not be empty")
	}
}

func TestVersionDefaultValues(t *testing.T) {
	// Default values when not injected via ldflags
	// These are the compile-time defaults
	tests := []struct {
		name     string
		got      string
		notEmpty bool
	}{
		{"Version is set", Version, true},
		{"BuildTime is set", BuildTime, true},
		{"GitCommit is set", GitCommit, true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if tt.notEmpty && tt.got == "" {
				t.Errorf("Expected non-empty value")
			}
		})
	}
}
