// Package main provides the entry point for the Cyber-Red drop box binary.
// Drop boxes are lightweight, cross-platform agents that connect to the C2 server
// via mTLS WebSocket and can execute WiFi toolkit commands.
package main

import (
	"flag"
	"fmt"
	"io"
	"os"

	"github.com/cyber-red/dropbox/internal"
)

// CLI holds the command-line interface configuration for testing.
type CLI struct {
	args   []string
	stdout io.Writer
	stderr io.Writer
}

// NewCLI creates a new CLI with the given arguments and output writers.
func NewCLI(args []string, stdout, stderr io.Writer) *CLI {
	return &CLI{
		args:   args,
		stdout: stdout,
		stderr: stderr,
	}
}

// Run executes the CLI and returns an exit code.
func (c *CLI) Run() int {
	// Create a new FlagSet for testability
	fs := flag.NewFlagSet("dropbox", flag.ContinueOnError)
	fs.SetOutput(c.stderr)

	versionFlag := fs.Bool("version", false, "Print version information and exit")
	helpFlag := fs.Bool("help", false, "Print help information and exit")
	configPath := fs.String("config", "", "Path to configuration file")

	// Custom usage function
	fs.Usage = func() {
		fmt.Fprintf(c.stderr, "Cyber-Red Drop Box v%s\n\n", internal.Version)
		fmt.Fprintf(c.stderr, "A lightweight, cross-platform agent for Cyber-Red engagements.\n\n")
		fmt.Fprintf(c.stderr, "Usage:\n")
		fmt.Fprintf(c.stderr, "  dropbox [options]\n\n")
		fmt.Fprintf(c.stderr, "Options:\n")
		fs.PrintDefaults()
		fmt.Fprintf(c.stderr, "\nExamples:\n")
		fmt.Fprintf(c.stderr, "  dropbox --config /path/to/config.yaml\n")
		fmt.Fprintf(c.stderr, "  dropbox --version\n")
	}

	// Parse arguments (skip program name if present)
	args := c.args
	if len(args) > 0 && args[0] == "dropbox" {
		args = args[1:]
	}

	if err := fs.Parse(args); err != nil {
		return 1
	}

	// Handle version flag
	if *versionFlag {
		fmt.Fprintf(c.stdout, "Cyber-Red Drop Box\n")
		fmt.Fprintf(c.stdout, "  Version:    %s\n", internal.Version)
		fmt.Fprintf(c.stdout, "  Build Time: %s\n", internal.BuildTime)
		fmt.Fprintf(c.stdout, "  Git Commit: %s\n", internal.GitCommit)
		return 0
	}

	// Handle help flag
	if *helpFlag {
		fs.Usage()
		return 0
	}

	// Validate configuration
	if *configPath == "" {
		fmt.Fprintf(c.stderr, "Error: No configuration file specified.\n")
		fmt.Fprintf(c.stderr, "Use --config to specify a configuration file.\n")
		fmt.Fprintf(c.stderr, "Use --help for more information.\n")
		return 1
	}

	// Configuration file specified but not yet implemented
	// This is expected behavior for Story 12.5 - actual C2 connection is Story 12.6
	fmt.Fprintf(c.stderr, "Error: C2 client not yet implemented.\n")
	fmt.Fprintf(c.stderr, "Configuration file: %s\n", *configPath)
	fmt.Fprintf(c.stderr, "This feature will be available in Story 12.6 (Drop Box mTLS Client).\n")
	return 1
}

func main() {
	cli := NewCLI(os.Args[1:], os.Stdout, os.Stderr)
	os.Exit(cli.Run())
}
