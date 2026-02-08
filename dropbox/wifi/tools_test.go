package wifi

import (
	"errors"
	"strings"
	"testing"
)

func TestToolConstants(t *testing.T) {
	tests := []struct {
		tool     Tool
		expected string
	}{
		{ToolAircrackNG, "aircrack-ng"},
		{ToolAirodumpNG, "airodump-ng"},
		{ToolAireplayNG, "aireplay-ng"},
		{ToolAirmonNG, "airmon-ng"},
		{ToolWifite, "wifite"},
		{ToolKismet, "kismet"},
	}

	for _, tt := range tests {
		t.Run(string(tt.tool), func(t *testing.T) {
			if string(tt.tool) != tt.expected {
				t.Errorf("Tool = %q, want %q", tt.tool, tt.expected)
			}
		})
	}
}

func TestRequiredTools(t *testing.T) {
	if len(RequiredTools) != 4 {
		t.Errorf("len(RequiredTools) = %d, want 4", len(RequiredTools))
	}

	// Verify all required tools are aircrack-ng suite
	for _, tool := range RequiredTools {
		if !strings.Contains(string(tool), "air") {
			t.Errorf("unexpected required tool: %s", tool)
		}
	}
}

func TestAllTools(t *testing.T) {
	all := AllTools()
	expected := len(RequiredTools) + len(OptionalTools)
	if len(all) != expected {
		t.Errorf("len(AllTools()) = %d, want %d", len(all), expected)
	}
}

func TestNewToolChecker(t *testing.T) {
	executor := NewMockExecutor()
	checker := NewToolChecker(executor)

	if checker == nil {
		t.Fatal("NewToolChecker returned nil")
	}
	if checker.executor != executor {
		t.Error("executor not set correctly")
	}
}

func TestToolChecker_CheckTool_Available(t *testing.T) {
	executor := NewMockExecutor()
	checker := NewToolChecker(executor)

	// Mock 'which aircrack-ng' returning a path
	executor.SetResponse("which", []byte("/usr/bin/aircrack-ng\n"), nil)
	// Mock version output
	executor.SetResponseWithArgs("aircrack-ng --version", []byte("Aircrack-ng 1.7\n"), nil)

	status, err := checker.CheckTool(ToolAircrackNG)
	if err != nil {
		t.Fatalf("CheckTool error = %v", err)
	}

	if !status.Available {
		t.Error("status.Available should be true")
	}
	if status.Path != "/usr/bin/aircrack-ng" {
		t.Errorf("status.Path = %q, want %q", status.Path, "/usr/bin/aircrack-ng")
	}
	if status.Tool != ToolAircrackNG {
		t.Errorf("status.Tool = %q, want %q", status.Tool, ToolAircrackNG)
	}
}

func TestToolChecker_CheckTool_NotAvailable(t *testing.T) {
	executor := NewMockExecutor()
	checker := NewToolChecker(executor)

	// Mock 'which' returning error (tool not found)
	executor.SetResponse("which", nil, errors.New("not found"))

	status, err := checker.CheckTool(ToolWifite)
	if err != nil {
		t.Fatalf("CheckTool error = %v", err)
	}

	if status.Available {
		t.Error("status.Available should be false")
	}
	if status.Path != "" {
		t.Errorf("status.Path should be empty, got %q", status.Path)
	}
}

func TestToolChecker_CheckAllTools(t *testing.T) {
	executor := NewMockExecutor()
	checker := NewToolChecker(executor)

	// Mock all tools as available
	executor.SetResponse("which", []byte("/usr/bin/tool\n"), nil)

	result, err := checker.CheckAllTools()
	if err != nil {
		t.Fatalf("CheckAllTools error = %v", err)
	}

	expectedCount := len(AllTools())
	if len(result) != expectedCount {
		t.Errorf("len(result) = %d, want %d", len(result), expectedCount)
	}

	// Verify all tools are in result
	for _, tool := range AllTools() {
		if _, ok := result[tool]; !ok {
			t.Errorf("tool %s not in result", tool)
		}
	}
}

func TestToolChecker_CheckRequiredTools_AllPresent(t *testing.T) {
	executor := NewMockExecutor()
	checker := NewToolChecker(executor)

	// Mock all required tools as available
	executor.SetResponse("which", []byte("/usr/bin/tool\n"), nil)

	err := checker.CheckRequiredTools()
	if err != nil {
		t.Errorf("CheckRequiredTools should return nil when all present, got: %v", err)
	}
}

func TestToolChecker_CheckRequiredTools_Missing(t *testing.T) {
	executor := NewMockExecutor()
	checker := NewToolChecker(executor)

	// Mock 'which' returning error (tools not found)
	executor.SetResponse("which", nil, errors.New("not found"))

	err := checker.CheckRequiredTools()
	if err == nil {
		t.Fatal("CheckRequiredTools should return error when tools missing")
	}

	var toolErr *ErrToolNotFound
	if !errors.As(err, &toolErr) {
		t.Errorf("error should be ErrToolNotFound, got: %T", err)
	}
}

func TestErrToolNotFound_Error(t *testing.T) {
	tests := []struct {
		name        string
		tool        Tool
		installHint string
		wantContain string
	}{
		{
			name:        "with hint",
			tool:        ToolAircrackNG,
			installHint: "apt install aircrack-ng",
			wantContain: "install with:",
		},
		{
			name:        "without hint",
			tool:        ToolAircrackNG,
			installHint: "",
			wantContain: "required tool not found",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := &ErrToolNotFound{
				Tool:        tt.tool,
				InstallHint: tt.installHint,
			}
			if !strings.Contains(err.Error(), tt.wantContain) {
				t.Errorf("Error() = %q, should contain %q", err.Error(), tt.wantContain)
			}
			if !strings.Contains(err.Error(), string(tt.tool)) {
				t.Errorf("Error() = %q, should contain tool name", err.Error())
			}
		})
	}
}

func TestGetInstallHint(t *testing.T) {
	tests := []struct {
		tool     Tool
		wantHint string
	}{
		{ToolAircrackNG, "apt install aircrack-ng"},
		{ToolAirodumpNG, "apt install aircrack-ng"},
		{ToolAireplayNG, "apt install aircrack-ng"},
		{ToolAirmonNG, "apt install aircrack-ng"},
		{ToolWifite, "apt install wifite"},
		{ToolKismet, "apt install kismet"},
		{Tool("unknown"), ""},
	}

	for _, tt := range tests {
		t.Run(string(tt.tool), func(t *testing.T) {
			hint := GetInstallHint(tt.tool)
			if hint != tt.wantHint {
				t.Errorf("GetInstallHint(%s) = %q, want %q", tt.tool, hint, tt.wantHint)
			}
		})
	}
}

func TestToolStatus_Struct(t *testing.T) {
	status := ToolStatus{
		Tool:      ToolAircrackNG,
		Available: true,
		Path:      "/usr/bin/aircrack-ng",
		Version:   "1.7",
	}

	if status.Tool != ToolAircrackNG {
		t.Errorf("Tool = %q, want %q", status.Tool, ToolAircrackNG)
	}
	if !status.Available {
		t.Error("Available should be true")
	}
	if status.Path != "/usr/bin/aircrack-ng" {
		t.Errorf("Path = %q, want %q", status.Path, "/usr/bin/aircrack-ng")
	}
	if status.Version != "1.7" {
		t.Errorf("Version = %q, want %q", status.Version, "1.7")
	}
}

func TestParseVersionOutput(t *testing.T) {
	tests := []struct {
		name    string
		output  string
		tool    Tool
		want    string
	}{
		{
			name:   "aircrack-ng version",
			output: "Aircrack-ng 1.7",
			tool:   ToolAircrackNG,
			want:   "1.7",
		},
		{
			name:   "wifite version",
			output: "wifite 2.6.0",
			tool:   ToolWifite,
			want:   "2.6.0",
		},
		{
			name:   "kismet version",
			output: "Kismet 2022-08-R1",
			tool:   ToolKismet,
			want:   "2022-08-R1",
		},
		{
			name:   "empty output",
			output: "",
			tool:   ToolAircrackNG,
			want:   "",
		},
		{
			name:   "unknown format",
			output: "some random output",
			tool:   ToolAircrackNG,
			want:   "",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := parseVersionOutput(tt.output, tt.tool)
			if got != tt.want {
				t.Errorf("parseVersionOutput() = %q, want %q", got, tt.want)
			}
		})
	}
}
