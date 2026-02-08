package wifi

import (
	"testing"
)

func TestNewCommandHandler(t *testing.T) {
	executor := NewMockExecutor()
	toolkit := NewToolkitWithExecutor(executor)
	handler := NewCommandHandler(toolkit)

	if handler == nil {
		t.Fatal("NewCommandHandler returned nil")
	}
	if handler.toolkit != toolkit {
		t.Error("toolkit not set correctly")
	}
}

func TestCommandHandler_HandleCommand_UnknownCommand(t *testing.T) {
	executor := NewMockExecutor()
	toolkit := NewToolkitWithExecutor(executor)
	handler := NewCommandHandler(toolkit)

	result := handler.HandleCommand("unknown_command", nil)

	if result.Success {
		t.Error("unknown command should fail")
	}
	if result.Error == "" {
		t.Error("error message should be set")
	}
}

func TestCommandHandler_HandleScan_MissingInterface(t *testing.T) {
	executor := NewMockExecutor()
	toolkit := NewToolkitWithExecutor(executor)
	handler := NewCommandHandler(toolkit)

	result := handler.HandleCommand("wifi_scan", map[string]any{})

	if result.Success {
		t.Error("scan without interface should fail")
	}
	if result.Error == "" {
		t.Error("error message should be set")
	}
}

func TestCommandHandler_HandleDeauth_MissingArgs(t *testing.T) {
	executor := NewMockExecutor()
	toolkit := NewToolkitWithExecutor(executor)
	handler := NewCommandHandler(toolkit)

	// Missing interface
	result := handler.HandleCommand("wifi_deauth", map[string]any{
		"bssid": "AA:BB:CC:DD:EE:FF",
	})
	if result.Success {
		t.Error("deauth without interface should fail")
	}

	// Missing bssid
	result = handler.HandleCommand("wifi_deauth", map[string]any{
		"interface": "wlan0mon",
	})
	if result.Success {
		t.Error("deauth without bssid should fail")
	}
}

func TestCommandHandler_HandleDeauth_Success(t *testing.T) {
	executor := NewMockExecutor()
	toolkit := NewToolkitWithExecutor(executor)
	handler := NewCommandHandler(toolkit)

	// Mock aireplay-ng success
	executor.SetResponse("aireplay-ng", []byte("Sending 10 DeAuth"), nil)

	result := handler.HandleCommand("wifi_deauth", map[string]any{
		"interface": "wlan0mon",
		"bssid":     "AA:BB:CC:DD:EE:FF",
		"count":     10,
	})

	if !result.Success {
		t.Errorf("deauth should succeed, got error: %s", result.Error)
	}
}

func TestCommandHandler_HandleCapture_MissingArgs(t *testing.T) {
	executor := NewMockExecutor()
	toolkit := NewToolkitWithExecutor(executor)
	handler := NewCommandHandler(toolkit)

	// Missing interface
	result := handler.HandleCommand("wifi_capture", map[string]any{
		"bssid":   "AA:BB:CC:DD:EE:FF",
		"channel": 6,
	})
	if result.Success {
		t.Error("capture without interface should fail")
	}

	// Missing bssid
	result = handler.HandleCommand("wifi_capture", map[string]any{
		"interface": "wlan0mon",
		"channel":   6,
	})
	if result.Success {
		t.Error("capture without bssid should fail")
	}

	// Missing channel
	result = handler.HandleCommand("wifi_capture", map[string]any{
		"interface": "wlan0mon",
		"bssid":     "AA:BB:CC:DD:EE:FF",
	})
	if result.Success {
		t.Error("capture without channel should fail")
	}
}

func TestCommandHandler_HandleCrack_MissingArgs(t *testing.T) {
	executor := NewMockExecutor()
	toolkit := NewToolkitWithExecutor(executor)
	handler := NewCommandHandler(toolkit)

	// Missing capture_file
	result := handler.HandleCommand("wifi_crack", map[string]any{
		"wordlist": "/path/to/wordlist.txt",
	})
	if result.Success {
		t.Error("crack without capture_file should fail")
	}

	// Missing wordlist
	result = handler.HandleCommand("wifi_crack", map[string]any{
		"capture_file": "/path/to/capture.cap",
	})
	if result.Success {
		t.Error("crack without wordlist should fail")
	}
}

func TestCommandHandler_HandleMonitorOn_MissingInterface(t *testing.T) {
	executor := NewMockExecutor()
	toolkit := NewToolkitWithExecutor(executor)
	handler := NewCommandHandler(toolkit)

	result := handler.HandleCommand("wifi_monitor_on", map[string]any{})

	if result.Success {
		t.Error("monitor_on without interface should fail")
	}
}

func TestCommandHandler_HandleMonitorOff_MissingInterface(t *testing.T) {
	executor := NewMockExecutor()
	toolkit := NewToolkitWithExecutor(executor)
	handler := NewCommandHandler(toolkit)

	result := handler.HandleCommand("wifi_monitor_off", map[string]any{})

	if result.Success {
		t.Error("monitor_off without interface should fail")
	}
}

func TestGetStringArg(t *testing.T) {
	args := map[string]any{
		"key1": "value1",
		"key2": 123,
	}

	// Existing string key
	val, ok := getStringArg(args, "key1")
	if !ok || val != "value1" {
		t.Errorf("getStringArg(key1) = %q, %v; want 'value1', true", val, ok)
	}

	// Non-string key
	val, ok = getStringArg(args, "key2")
	if ok {
		t.Error("getStringArg should return false for non-string value")
	}

	// Missing key
	val, ok = getStringArg(args, "key3")
	if ok {
		t.Error("getStringArg should return false for missing key")
	}

	// Nil args
	val, ok = getStringArg(nil, "key1")
	if ok {
		t.Error("getStringArg should return false for nil args")
	}
}

func TestGetIntArg(t *testing.T) {
	args := map[string]any{
		"int":     10,
		"int64":   int64(20),
		"float64": float64(30),
		"string":  "not a number",
	}

	// int type
	if val := getIntArg(args, "int", 0); val != 10 {
		t.Errorf("getIntArg(int) = %d, want 10", val)
	}

	// int64 type
	if val := getIntArg(args, "int64", 0); val != 20 {
		t.Errorf("getIntArg(int64) = %d, want 20", val)
	}

	// float64 type (common from JSON)
	if val := getIntArg(args, "float64", 0); val != 30 {
		t.Errorf("getIntArg(float64) = %d, want 30", val)
	}

	// string type (should return default)
	if val := getIntArg(args, "string", 99); val != 99 {
		t.Errorf("getIntArg(string) = %d, want 99 (default)", val)
	}

	// Missing key (should return default)
	if val := getIntArg(args, "missing", 42); val != 42 {
		t.Errorf("getIntArg(missing) = %d, want 42 (default)", val)
	}

	// Nil args
	if val := getIntArg(nil, "key", 100); val != 100 {
		t.Errorf("getIntArg(nil) = %d, want 100 (default)", val)
	}
}

func TestIsWiFiCommand(t *testing.T) {
	tests := []struct {
		command string
		want    bool
	}{
		{"wifi_scan", true},
		{"wifi_deauth", true},
		{"wifi_capture", true},
		{"wifi_crack", true},
		{"wifi_monitor_on", true},
		{"wifi_monitor_off", true},
		{"shell_exec", false},
		{"file_upload", false},
		{"unknown", false},
		{"", false},
	}

	for _, tt := range tests {
		t.Run(tt.command, func(t *testing.T) {
			got := IsWiFiCommand(tt.command)
			if got != tt.want {
				t.Errorf("IsWiFiCommand(%q) = %v, want %v", tt.command, got, tt.want)
			}
		})
	}
}

func TestGetSupportedCommands(t *testing.T) {
	commands := GetSupportedCommands()

	if len(commands) != 6 {
		t.Errorf("len(GetSupportedCommands()) = %d, want 6", len(commands))
	}

	// Verify all expected commands are present
	expected := map[C2CommandType]bool{
		C2CommandWiFiScan:       false,
		C2CommandWiFiDeauth:     false,
		C2CommandWiFiCapture:    false,
		C2CommandWiFiCrack:      false,
		C2CommandWiFiMonitorOn:  false,
		C2CommandWiFiMonitorOff: false,
	}

	for _, cmd := range commands {
		if _, ok := expected[cmd]; ok {
			expected[cmd] = true
		} else {
			t.Errorf("unexpected command in list: %s", cmd)
		}
	}

	for cmd, found := range expected {
		if !found {
			t.Errorf("expected command not found: %s", cmd)
		}
	}
}

func TestC2CommandTypes(t *testing.T) {
	tests := []struct {
		cmd  C2CommandType
		want string
	}{
		{C2CommandWiFiScan, "wifi_scan"},
		{C2CommandWiFiDeauth, "wifi_deauth"},
		{C2CommandWiFiCapture, "wifi_capture"},
		{C2CommandWiFiCrack, "wifi_crack"},
		{C2CommandWiFiMonitorOn, "wifi_monitor_on"},
		{C2CommandWiFiMonitorOff, "wifi_monitor_off"},
	}

	for _, tt := range tests {
		t.Run(string(tt.cmd), func(t *testing.T) {
			if string(tt.cmd) != tt.want {
				t.Errorf("C2CommandType = %q, want %q", tt.cmd, tt.want)
			}
		})
	}
}
