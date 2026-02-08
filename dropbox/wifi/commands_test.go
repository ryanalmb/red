package wifi

import (
	"testing"
)

func TestCommandTypes(t *testing.T) {
	tests := []struct {
		cmdType  CommandType
		expected string
	}{
		{CommandScan, "scan"},
		{CommandCapture, "capture"},
		{CommandDeauth, "deauth"},
		{CommandCrack, "crack"},
		{CommandMonitor, "monitor"},
	}

	for _, tt := range tests {
		t.Run(string(tt.cmdType), func(t *testing.T) {
			if string(tt.cmdType) != tt.expected {
				t.Errorf("CommandType = %q, want %q", tt.cmdType, tt.expected)
			}
		})
	}
}

func TestNewCommand(t *testing.T) {
	cmd := NewCommand(CommandScan, "TargetNetwork")

	if cmd == nil {
		t.Fatal("NewCommand returned nil")
	}
	if cmd.Type != CommandScan {
		t.Errorf("Type = %v, want %v", cmd.Type, CommandScan)
	}
	if cmd.Target != "TargetNetwork" {
		t.Errorf("Target = %q, want %q", cmd.Target, "TargetNetwork")
	}
	if cmd.Options == nil {
		t.Error("Options should be initialized")
	}
	if len(cmd.Options) != 0 {
		t.Error("Options should be empty initially")
	}
}

func TestCommandSetOption(t *testing.T) {
	cmd := NewCommand(CommandCapture, "AA:BB:CC:DD:EE:FF")

	result := cmd.SetOption("channel", 6)

	// Should return the same command for chaining
	if result != cmd {
		t.Error("SetOption should return the same command for chaining")
	}

	if cmd.Options["channel"] != 6 {
		t.Errorf("Options[channel] = %v, want %v", cmd.Options["channel"], 6)
	}

	// Test chaining
	cmd.SetOption("timeout", 30).SetOption("verbose", true)

	if cmd.Options["timeout"] != 30 {
		t.Errorf("Options[timeout] = %v, want %v", cmd.Options["timeout"], 30)
	}
	if cmd.Options["verbose"] != true {
		t.Errorf("Options[verbose] = %v, want %v", cmd.Options["verbose"], true)
	}
}

func TestCommandSetOptionOverwrite(t *testing.T) {
	cmd := NewCommand(CommandDeauth, "target")
	cmd.SetOption("key", "value1")
	cmd.SetOption("key", "value2")

	if cmd.Options["key"] != "value2" {
		t.Errorf("Options[key] = %v, want %v", cmd.Options["key"], "value2")
	}
}

func TestNewResult(t *testing.T) {
	result := NewResult(true, "scan complete")

	if result == nil {
		t.Fatal("NewResult returned nil")
	}
	if !result.Success {
		t.Error("Success should be true")
	}
	if result.Output != "scan complete" {
		t.Errorf("Output = %q, want %q", result.Output, "scan complete")
	}
	if result.Error != "" {
		t.Error("Error should be empty initially")
	}
	if result.Data != nil {
		t.Error("Data should be nil initially")
	}
}

func TestResultWithError(t *testing.T) {
	result := NewResult(true, "some output")
	returned := result.WithError("something went wrong")

	// Should return the same result for chaining
	if returned != result {
		t.Error("WithError should return the same result for chaining")
	}
	if result.Success {
		t.Error("Success should be false after WithError")
	}
	if result.Error != "something went wrong" {
		t.Errorf("Error = %q, want %q", result.Error, "something went wrong")
	}
}

func TestResultWithData(t *testing.T) {
	result := NewResult(true, "output")
	networks := []Network{
		{BSSID: "AA:BB:CC:DD:EE:FF", ESSID: "Test"},
	}
	returned := result.WithData(networks)

	// Should return the same result for chaining
	if returned != result {
		t.Error("WithData should return the same result for chaining")
	}
	if result.Data == nil {
		t.Error("Data should not be nil after WithData")
	}

	data, ok := result.Data.([]Network)
	if !ok {
		t.Fatal("Data should be []Network")
	}
	if len(data) != 1 {
		t.Errorf("len(Data) = %d, want %d", len(data), 1)
	}
	if data[0].ESSID != "Test" {
		t.Errorf("Data[0].ESSID = %q, want %q", data[0].ESSID, "Test")
	}
}

func TestResultChaining(t *testing.T) {
	result := NewResult(false, "failed").
		WithError("timeout").
		WithData(map[string]string{"reason": "network unreachable"})

	if result.Success {
		t.Error("Success should be false")
	}
	if result.Output != "failed" {
		t.Errorf("Output = %q, want %q", result.Output, "failed")
	}
	if result.Error != "timeout" {
		t.Errorf("Error = %q, want %q", result.Error, "timeout")
	}
	if result.Data == nil {
		t.Error("Data should not be nil")
	}
}
