// Package wifi provides wrappers for WiFi security tools.
package wifi

import (
	"fmt"
	"strings"
)

// Tool represents a WiFi security tool.
type Tool string

const (
	// ToolAircrackNG is the aircrack-ng password cracker.
	ToolAircrackNG Tool = "aircrack-ng"

	// ToolAirodumpNG is the airodump-ng network scanner.
	ToolAirodumpNG Tool = "airodump-ng"

	// ToolAireplayNG is the aireplay-ng packet injector.
	ToolAireplayNG Tool = "aireplay-ng"

	// ToolAirmonNG is the airmon-ng monitor mode manager.
	ToolAirmonNG Tool = "airmon-ng"

	// ToolWifite is the wifite automated WiFi attack tool.
	ToolWifite Tool = "wifite"

	// ToolKismet is the kismet wireless network detector.
	ToolKismet Tool = "kismet"
)

// RequiredTools lists the tools required for basic WiFi operations.
var RequiredTools = []Tool{
	ToolAircrackNG,
	ToolAirodumpNG,
	ToolAireplayNG,
	ToolAirmonNG,
}

// OptionalTools lists tools that enhance functionality but aren't required.
var OptionalTools = []Tool{
	ToolWifite,
	ToolKismet,
}

// AllTools returns all known WiFi tools.
func AllTools() []Tool {
	return append(RequiredTools, OptionalTools...)
}

// ErrToolNotFound is returned when a required tool is not installed.
type ErrToolNotFound struct {
	Tool        Tool
	InstallHint string
}

func (e *ErrToolNotFound) Error() string {
	if e.InstallHint != "" {
		return fmt.Sprintf("required tool not found: %s (install with: %s)", e.Tool, e.InstallHint)
	}
	return fmt.Sprintf("required tool not found: %s", e.Tool)
}

// ToolStatus represents the availability status of a tool.
type ToolStatus struct {
	Tool      Tool
	Available bool
	Path      string
	Version   string
}

// ToolChecker checks for tool availability.
type ToolChecker struct {
	executor CommandExecutor
}

// NewToolChecker creates a new ToolChecker with the given executor.
func NewToolChecker(executor CommandExecutor) *ToolChecker {
	return &ToolChecker{
		executor: executor,
	}
}

// CheckTool checks if a specific tool is available.
func (c *ToolChecker) CheckTool(tool Tool) (*ToolStatus, error) {
	status := &ToolStatus{
		Tool:      tool,
		Available: false,
	}

	// Use 'which' to find the tool path
	output, err := c.executor.Run("which", string(tool))
	if err != nil {
		// Tool not found
		return status, nil
	}

	path := strings.TrimSpace(string(output))
	if path == "" {
		return status, nil
	}

	status.Available = true
	status.Path = path

	// Try to get version
	version := c.getToolVersion(tool)
	if version != "" {
		status.Version = version
	}

	return status, nil
}

// getToolVersion attempts to get the version of a tool.
func (c *ToolChecker) getToolVersion(tool Tool) string {
	var output []byte
	var err error

	switch tool {
	case ToolAircrackNG:
		output, err = c.executor.Run("aircrack-ng", "--version")
	case ToolAirodumpNG, ToolAireplayNG, ToolAirmonNG:
		// These tools are part of aircrack-ng suite and share version
		output, err = c.executor.Run(string(tool), "--help")
	case ToolWifite:
		output, err = c.executor.Run("wifite", "--version")
	case ToolKismet:
		output, err = c.executor.Run("kismet", "--version")
	default:
		return ""
	}

	if err != nil {
		return ""
	}

	return parseVersionOutput(string(output), tool)
}

// parseVersionOutput extracts version from tool output.
func parseVersionOutput(output string, tool Tool) string {
	lines := strings.Split(output, "\n")
	if len(lines) == 0 {
		return ""
	}

	// Most tools output version in first line
	firstLine := strings.TrimSpace(lines[0])

	// Look for version patterns
	switch tool {
	case ToolAircrackNG:
		// "Aircrack-ng 1.7"
		if strings.Contains(firstLine, "Aircrack-ng") {
			parts := strings.Fields(firstLine)
			if len(parts) >= 2 {
				return parts[len(parts)-1]
			}
		}
	case ToolWifite:
		// "wifite 2.6.0"
		if strings.Contains(strings.ToLower(firstLine), "wifite") {
			parts := strings.Fields(firstLine)
			if len(parts) >= 2 {
				return parts[len(parts)-1]
			}
		}
	case ToolKismet:
		// "Kismet 2022-08-R1"
		if strings.Contains(firstLine, "Kismet") {
			parts := strings.Fields(firstLine)
			if len(parts) >= 2 {
				return parts[len(parts)-1]
			}
		}
	}

	return ""
}

// CheckAllTools checks availability of all required and optional tools.
func (c *ToolChecker) CheckAllTools() (map[Tool]*ToolStatus, error) {
	result := make(map[Tool]*ToolStatus)

	for _, tool := range AllTools() {
		status, err := c.CheckTool(tool)
		if err != nil {
			return nil, err
		}
		result[tool] = status
	}

	return result, nil
}

// CheckRequiredTools checks if all required tools are available.
// Returns an error listing all missing tools if any are not found.
func (c *ToolChecker) CheckRequiredTools() error {
	var missing []Tool

	for _, tool := range RequiredTools {
		status, err := c.CheckTool(tool)
		if err != nil {
			return err
		}
		if !status.Available {
			missing = append(missing, tool)
		}
	}

	if len(missing) > 0 {
		return &ErrToolNotFound{
			Tool:        missing[0],
			InstallHint: "apt install aircrack-ng",
		}
	}

	return nil
}

// GetInstallHint returns installation instructions for a tool.
func GetInstallHint(tool Tool) string {
	switch tool {
	case ToolAircrackNG, ToolAirodumpNG, ToolAireplayNG, ToolAirmonNG:
		return "apt install aircrack-ng"
	case ToolWifite:
		return "apt install wifite"
	case ToolKismet:
		return "apt install kismet"
	default:
		return ""
	}
}
