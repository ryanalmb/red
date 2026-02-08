package main

import (
	"bytes"
	"strings"
	"testing"

	"github.com/cyber-red/dropbox/internal"
)

func TestNewCLI(t *testing.T) {
	var stdout, stderr bytes.Buffer
	args := []string{"--version"}

	cli := NewCLI(args, &stdout, &stderr)

	if cli == nil {
		t.Fatal("NewCLI returned nil")
	}
	if len(cli.args) != 1 || cli.args[0] != "--version" {
		t.Errorf("args = %v, want [--version]", cli.args)
	}
	if cli.stdout != &stdout {
		t.Error("stdout not set correctly")
	}
	if cli.stderr != &stderr {
		t.Error("stderr not set correctly")
	}
}

func TestCLIVersionFlag(t *testing.T) {
	var stdout, stderr bytes.Buffer
	cli := NewCLI([]string{"--version"}, &stdout, &stderr)

	exitCode := cli.Run()

	if exitCode != 0 {
		t.Errorf("exit code = %d, want 0", exitCode)
	}

	output := stdout.String()
	if !strings.Contains(output, "Cyber-Red Drop Box") {
		t.Errorf("expected 'Cyber-Red Drop Box' in output, got: %s", output)
	}
	if !strings.Contains(output, "Version:") {
		t.Errorf("expected 'Version:' in output, got: %s", output)
	}
	if !strings.Contains(output, internal.Version) {
		t.Errorf("expected version '%s' in output, got: %s", internal.Version, output)
	}
	if !strings.Contains(output, "Build Time:") {
		t.Errorf("expected 'Build Time:' in output, got: %s", output)
	}
	if !strings.Contains(output, "Git Commit:") {
		t.Errorf("expected 'Git Commit:' in output, got: %s", output)
	}
}

func TestCLIHelpFlag(t *testing.T) {
	var stdout, stderr bytes.Buffer
	cli := NewCLI([]string{"--help"}, &stdout, &stderr)

	exitCode := cli.Run()

	if exitCode != 0 {
		t.Errorf("exit code = %d, want 0", exitCode)
	}

	output := stderr.String()
	if !strings.Contains(output, "Cyber-Red Drop Box") {
		t.Errorf("expected 'Cyber-Red Drop Box' in output, got: %s", output)
	}
	if !strings.Contains(output, "Usage:") {
		t.Errorf("expected 'Usage:' in output, got: %s", output)
	}
	if !strings.Contains(output, "-config") {
		t.Errorf("expected '-config' in output, got: %s", output)
	}
	if !strings.Contains(output, "-version") {
		t.Errorf("expected '-version' in output, got: %s", output)
	}
	if !strings.Contains(output, "-help") {
		t.Errorf("expected '-help' in output, got: %s", output)
	}
	if !strings.Contains(output, "Examples:") {
		t.Errorf("expected 'Examples:' in output, got: %s", output)
	}
}

func TestCLINoConfig(t *testing.T) {
	var stdout, stderr bytes.Buffer
	cli := NewCLI([]string{}, &stdout, &stderr)

	exitCode := cli.Run()

	if exitCode != 1 {
		t.Errorf("exit code = %d, want 1", exitCode)
	}

	output := stderr.String()
	if !strings.Contains(output, "No configuration file specified") {
		t.Errorf("expected 'No configuration file specified' in output, got: %s", output)
	}
	if !strings.Contains(output, "Use --config") {
		t.Errorf("expected 'Use --config' in output, got: %s", output)
	}
	if !strings.Contains(output, "Use --help") {
		t.Errorf("expected 'Use --help' in output, got: %s", output)
	}
}

func TestCLIWithConfig(t *testing.T) {
	var stdout, stderr bytes.Buffer
	cli := NewCLI([]string{"--config", "/path/to/config.yaml"}, &stdout, &stderr)

	exitCode := cli.Run()

	// Should exit with 1 because C2 client is not yet implemented
	if exitCode != 1 {
		t.Errorf("exit code = %d, want 1", exitCode)
	}

	output := stderr.String()
	if !strings.Contains(output, "C2 client not yet implemented") {
		t.Errorf("expected 'C2 client not yet implemented' in output, got: %s", output)
	}
	if !strings.Contains(output, "/path/to/config.yaml") {
		t.Errorf("expected config path in output, got: %s", output)
	}
	if !strings.Contains(output, "Story 12.6") {
		t.Errorf("expected 'Story 12.6' reference in output, got: %s", output)
	}
}

func TestCLIInvalidFlag(t *testing.T) {
	var stdout, stderr bytes.Buffer
	cli := NewCLI([]string{"--invalid-flag"}, &stdout, &stderr)

	exitCode := cli.Run()

	if exitCode != 1 {
		t.Errorf("exit code = %d, want 1", exitCode)
	}

	output := stderr.String()
	if !strings.Contains(output, "flag provided but not defined") {
		t.Errorf("expected flag error in output, got: %s", output)
	}
}

func TestCLIWithProgramName(t *testing.T) {
	// Test that program name is skipped if present
	var stdout, stderr bytes.Buffer
	cli := NewCLI([]string{"dropbox", "--version"}, &stdout, &stderr)

	exitCode := cli.Run()

	if exitCode != 0 {
		t.Errorf("exit code = %d, want 0", exitCode)
	}

	output := stdout.String()
	if !strings.Contains(output, "Cyber-Red Drop Box") {
		t.Errorf("expected 'Cyber-Red Drop Box' in output, got: %s", output)
	}
}

func TestCLIShortVersionFlag(t *testing.T) {
	var stdout, stderr bytes.Buffer
	cli := NewCLI([]string{"-version"}, &stdout, &stderr)

	exitCode := cli.Run()

	if exitCode != 0 {
		t.Errorf("exit code = %d, want 0", exitCode)
	}

	output := stdout.String()
	if !strings.Contains(output, "Cyber-Red Drop Box") {
		t.Errorf("expected 'Cyber-Red Drop Box' in output, got: %s", output)
	}
}

func TestCLIShortHelpFlag(t *testing.T) {
	var stdout, stderr bytes.Buffer
	cli := NewCLI([]string{"-help"}, &stdout, &stderr)

	exitCode := cli.Run()

	if exitCode != 0 {
		t.Errorf("exit code = %d, want 0", exitCode)
	}

	output := stderr.String()
	if !strings.Contains(output, "Usage:") {
		t.Errorf("expected 'Usage:' in output, got: %s", output)
	}
}

func TestCLIShortConfigFlag(t *testing.T) {
	var stdout, stderr bytes.Buffer
	cli := NewCLI([]string{"-config", "/path/to/config.yaml"}, &stdout, &stderr)

	exitCode := cli.Run()

	// Should exit with 1 because C2 client is not yet implemented
	if exitCode != 1 {
		t.Errorf("exit code = %d, want 1", exitCode)
	}

	output := stderr.String()
	if !strings.Contains(output, "C2 client not yet implemented") {
		t.Errorf("expected 'C2 client not yet implemented' in output, got: %s", output)
	}
}

func TestCLIConfigEqualsFormat(t *testing.T) {
	var stdout, stderr bytes.Buffer
	cli := NewCLI([]string{"--config=/path/to/config.yaml"}, &stdout, &stderr)

	exitCode := cli.Run()

	if exitCode != 1 {
		t.Errorf("exit code = %d, want 1", exitCode)
	}

	output := stderr.String()
	if !strings.Contains(output, "/path/to/config.yaml") {
		t.Errorf("expected config path in output, got: %s", output)
	}
}
