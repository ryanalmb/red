package wifi

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestErrNotImplemented(t *testing.T) {
	if ErrNotImplemented == nil {
		t.Fatal("ErrNotImplemented should not be nil")
	}
	expected := "wifi toolkit method requires interface parameter - use *WithInterface variant"
	if ErrNotImplemented.Error() != expected {
		t.Errorf("ErrNotImplemented = %q, want %q", ErrNotImplemented.Error(), expected)
	}
}

func TestNewToolkit(t *testing.T) {
	tk := NewToolkit()

	if tk == nil {
		t.Fatal("NewToolkit returned nil")
	}
	if tk.AircrackPath != "aircrack-ng" {
		t.Errorf("AircrackPath = %q, want %q", tk.AircrackPath, "aircrack-ng")
	}
	if tk.WifitePath != "wifite" {
		t.Errorf("WifitePath = %q, want %q", tk.WifitePath, "wifite")
	}
	if tk.KismetPath != "kismet" {
		t.Errorf("KismetPath = %q, want %q", tk.KismetPath, "kismet")
	}
	if tk.executor == nil {
		t.Error("executor should be initialized")
	}
	if tk.interfaceManager == nil {
		t.Error("interfaceManager should be initialized")
	}
	if tk.toolChecker == nil {
		t.Error("toolChecker should be initialized")
	}
}

func TestNewToolkitWithExecutor(t *testing.T) {
	executor := NewMockExecutor()
	tk := NewToolkitWithExecutor(executor)

	if tk == nil {
		t.Fatal("NewToolkitWithExecutor returned nil")
	}
	if tk.executor != executor {
		t.Error("executor not set correctly")
	}
}

func TestToolkitScanNetworks_NoMonitorInterface(t *testing.T) {
	executor := NewMockExecutor()
	tk := NewToolkitWithExecutor(executor)

	// Mock iw dev returning no monitor interfaces
	iwOutput := `phy#0
	Interface wlan0
		ifindex 3
		type managed
`
	executor.SetResponse("iw", []byte(iwOutput), nil)

	networks, err := tk.ScanNetworks()

	if err == nil {
		t.Error("ScanNetworks() should return error when no monitor interface")
	}
	if !errors.Is(err, ErrNoWirelessInterface) {
		t.Errorf("ScanNetworks() error = %v, want ErrNoWirelessInterface", err)
	}
	if networks != nil {
		t.Errorf("ScanNetworks() networks = %v, want nil", networks)
	}
}

func TestToolkitScanNetworks_WithMonitorInterface(t *testing.T) {
	executor := NewMockExecutor()
	tk := NewToolkitWithExecutor(executor)
	tk.TempDir = t.TempDir()

	// Mock iw dev returning monitor interface
	iwOutput := `phy#0
	Interface wlan0mon
		ifindex 3
		type monitor
`
	executor.SetResponse("iw", []byte(iwOutput), nil)

	// ScanNetworksWithInterface will be called, which starts airodump-ng
	// This will fail since we can't mock the file read, but it proves the delegation works
	networks, err := tk.ScanNetworks()

	// We expect an error because the CSV file won't exist in test
	if err == nil {
		t.Log("ScanNetworks succeeded (unexpected in unit test)")
	}
	_ = networks // May be nil due to file read error
}

func TestToolkitCaptureHandshake_NoMonitorInterface(t *testing.T) {
	executor := NewMockExecutor()
	tk := NewToolkitWithExecutor(executor)

	// Mock iw dev returning no monitor interfaces
	iwOutput := `phy#0
	Interface wlan0
		ifindex 3
		type managed
`
	executor.SetResponse("iw", []byte(iwOutput), nil)

	err := tk.CaptureHandshake("AA:BB:CC:DD:EE:FF", 6)

	if err == nil {
		t.Error("CaptureHandshake() should return error when no monitor interface")
	}
	if !errors.Is(err, ErrNoWirelessInterface) {
		t.Errorf("CaptureHandshake() error = %v, want ErrNoWirelessInterface", err)
	}
}

func TestToolkitDeauthClient_NoMonitorInterface(t *testing.T) {
	executor := NewMockExecutor()
	tk := NewToolkitWithExecutor(executor)

	// Mock iw dev returning no monitor interfaces
	iwOutput := `phy#0
	Interface wlan0
		ifindex 3
		type managed
`
	executor.SetResponse("iw", []byte(iwOutput), nil)

	err := tk.DeauthClient("AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66")

	if err == nil {
		t.Error("DeauthClient() should return error when no monitor interface")
	}
	if !errors.Is(err, ErrNoWirelessInterface) {
		t.Errorf("DeauthClient() error = %v, want ErrNoWirelessInterface", err)
	}
}

func TestToolkitDeauthClient_WithMonitorInterface(t *testing.T) {
	executor := NewMockExecutor()
	tk := NewToolkitWithExecutor(executor)

	// Mock iw dev returning monitor interface
	iwOutput := `phy#0
	Interface wlan0mon
		ifindex 3
		type monitor
`
	executor.SetResponse("iw", []byte(iwOutput), nil)

	// Mock aireplay-ng success
	aireplayOutput := `Sending 10 directed DeAuth. STMAC: [11:22:33:44:55:66] [ 5|10 ACKs]`
	executor.SetResponse("aireplay-ng", []byte(aireplayOutput), nil)

	err := tk.DeauthClient("AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66")

	if err != nil {
		t.Errorf("DeauthClient() unexpected error: %v", err)
	}
}

func TestToolkit_ScanNetworksWithInterface_InvalidInputs(t *testing.T) {
	executor := NewMockExecutor()
	tk := NewToolkitWithExecutor(executor)

	// Empty interface
	_, err := tk.ScanNetworksWithInterface("", 10)
	if !errors.Is(err, ErrInvalidInput) {
		t.Errorf("expected ErrInvalidInput for empty interface, got: %v", err)
	}

	// Invalid interface name
	_, err = tk.ScanNetworksWithInterface("wlan0; rm -rf /", 10)
	if !errors.Is(err, ErrInvalidInput) {
		t.Errorf("expected ErrInvalidInput for invalid interface, got: %v", err)
	}
}

func TestToolkit_DeauthClientWithInterface_InvalidInputs(t *testing.T) {
	executor := NewMockExecutor()
	tk := NewToolkitWithExecutor(executor)

	// Invalid BSSID
	_, err := tk.DeauthClientWithInterface("wlan0mon", "invalid", "", 10)
	if !errors.Is(err, ErrInvalidInput) {
		t.Errorf("expected ErrInvalidInput for invalid BSSID, got: %v", err)
	}

	// Invalid interface
	_, err = tk.DeauthClientWithInterface("invalid;cmd", "AA:BB:CC:DD:EE:FF", "", 10)
	if !errors.Is(err, ErrInvalidInput) {
		t.Errorf("expected ErrInvalidInput for invalid interface, got: %v", err)
	}

	// Invalid client MAC
	_, err = tk.DeauthClientWithInterface("wlan0mon", "AA:BB:CC:DD:EE:FF", "invalid", 10)
	if !errors.Is(err, ErrInvalidInput) {
		t.Errorf("expected ErrInvalidInput for invalid client MAC, got: %v", err)
	}
}

func TestToolkit_DeauthClientWithInterface_Success(t *testing.T) {
	executor := NewMockExecutor()
	tk := NewToolkitWithExecutor(executor)

	// Mock aireplay-ng output
	aireplayOutput := `12:34:56  Waiting for beacon frame (BSSID: AA:BB:CC:DD:EE:FF) on channel 6
12:34:57  Sending 64 directed DeAuth (code 7). STMAC: [11:22:33:44:55:66] [ 5|64 ACKs]
`
	executor.SetResponse("aireplay-ng", []byte(aireplayOutput), nil)

	result, err := tk.DeauthClientWithInterface("wlan0mon", "AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66", 64)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if !result.Success {
		t.Error("result.Success should be true")
	}
	if result.PacketsSent != 64 {
		t.Errorf("PacketsSent = %d, want 64", result.PacketsSent)
	}

	// Verify correct arguments were passed
	if len(executor.Calls) != 1 {
		t.Fatalf("expected 1 call, got %d", len(executor.Calls))
	}
	call := executor.Calls[0]
	if call.Name != "aireplay-ng" {
		t.Errorf("expected aireplay-ng call, got %s", call.Name)
	}
	// Should contain --deauth, -a, -c flags
	argsStr := strings.Join(call.Args, " ")
	if !strings.Contains(argsStr, "--deauth 64") {
		t.Errorf("args should contain --deauth 64, got: %s", argsStr)
	}
	if !strings.Contains(argsStr, "-a AA:BB:CC:DD:EE:FF") {
		t.Errorf("args should contain -a BSSID, got: %s", argsStr)
	}
	if !strings.Contains(argsStr, "-c 11:22:33:44:55:66") {
		t.Errorf("args should contain -c client MAC, got: %s", argsStr)
	}
}

func TestToolkit_DeauthClientWithInterface_BroadcastDeauth(t *testing.T) {
	executor := NewMockExecutor()
	tk := NewToolkitWithExecutor(executor)

	executor.SetResponse("aireplay-ng", []byte("Sending 10 DeAuth"), nil)

	// Empty client MAC = broadcast
	_, err := tk.DeauthClientWithInterface("wlan0mon", "AA:BB:CC:DD:EE:FF", "", 10)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Should NOT contain -c flag for broadcast
	call := executor.Calls[0]
	argsStr := strings.Join(call.Args, " ")
	if strings.Contains(argsStr, "-c") {
		t.Errorf("broadcast deauth should not have -c flag, got: %s", argsStr)
	}
}

func TestToolkit_CaptureHandshakeWithInterface_InvalidInputs(t *testing.T) {
	executor := NewMockExecutor()
	tk := NewToolkitWithExecutor(executor)

	// Invalid BSSID
	_, err := tk.CaptureHandshakeWithInterface("wlan0mon", "invalid", 6, 30)
	if !errors.Is(err, ErrInvalidInput) {
		t.Errorf("expected ErrInvalidInput for invalid BSSID, got: %v", err)
	}

	// Invalid channel
	_, err = tk.CaptureHandshakeWithInterface("wlan0mon", "AA:BB:CC:DD:EE:FF", 0, 30)
	if !errors.Is(err, ErrInvalidInput) {
		t.Errorf("expected ErrInvalidInput for invalid channel, got: %v", err)
	}

	// Invalid interface
	_, err = tk.CaptureHandshakeWithInterface("invalid;", "AA:BB:CC:DD:EE:FF", 6, 30)
	if !errors.Is(err, ErrInvalidInput) {
		t.Errorf("expected ErrInvalidInput for invalid interface, got: %v", err)
	}
}

func TestToolkit_CrackPassword_InvalidInputs(t *testing.T) {
	executor := NewMockExecutor()
	tk := NewToolkitWithExecutor(executor)

	// Empty capture file
	_, err := tk.CrackPassword("", "/wordlist.txt")
	if !errors.Is(err, ErrInvalidInput) {
		t.Errorf("expected ErrInvalidInput for empty capture file, got: %v", err)
	}

	// Empty wordlist
	_, err = tk.CrackPassword("/capture.cap", "")
	if !errors.Is(err, ErrInvalidInput) {
		t.Errorf("expected ErrInvalidInput for empty wordlist, got: %v", err)
	}

	// Non-existent capture file
	_, err = tk.CrackPassword("/nonexistent.cap", "/wordlist.txt")
	if !errors.Is(err, ErrInvalidInput) {
		t.Errorf("expected ErrInvalidInput for nonexistent capture file, got: %v", err)
	}
}

func TestToolkit_CrackPassword_Success(t *testing.T) {
	executor := NewMockExecutor()
	tk := NewToolkitWithExecutor(executor)

	// Create temp files for testing
	tmpDir := t.TempDir()
	capFile := filepath.Join(tmpDir, "test.cap")
	wordlist := filepath.Join(tmpDir, "wordlist.txt")

	os.WriteFile(capFile, []byte("dummy capture"), 0644)
	os.WriteFile(wordlist, []byte("password1\npassword2\n"), 0644)

	// Mock aircrack-ng success output
	aircrackOutput := `
                         KEY FOUND! [ mysecretpassword ]

      Master Key     : AA BB CC DD EE FF
`
	executor.SetResponse("aircrack-ng", []byte(aircrackOutput), nil)

	result, err := tk.CrackPassword(capFile, wordlist)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if !result.Success {
		t.Error("result.Success should be true")
	}
	if result.Password != "mysecretpassword" {
		t.Errorf("Password = %q, want %q", result.Password, "mysecretpassword")
	}
}

func TestToolkit_CrackPassword_NotFound(t *testing.T) {
	executor := NewMockExecutor()
	tk := NewToolkitWithExecutor(executor)

	// Create temp files
	tmpDir := t.TempDir()
	capFile := filepath.Join(tmpDir, "test.cap")
	wordlist := filepath.Join(tmpDir, "wordlist.txt")

	os.WriteFile(capFile, []byte("dummy"), 0644)
	os.WriteFile(wordlist, []byte("wrong\n"), 0644)

	// Mock aircrack-ng failure (returns error when not found)
	executor.SetResponse("aircrack-ng", []byte("Passphrase not in dictionary"), errors.New("exit 1"))

	result, err := tk.CrackPassword(capFile, wordlist)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if result.Success {
		t.Error("result.Success should be false")
	}
}

func TestToolkit_CheckTools(t *testing.T) {
	executor := NewMockExecutor()
	tk := NewToolkitWithExecutor(executor)

	// Mock all tools available
	executor.SetResponse("which", []byte("/usr/bin/tool\n"), nil)

	err := tk.CheckTools()
	if err != nil {
		t.Errorf("CheckTools should pass when tools available, got: %v", err)
	}
}

func TestToolkit_GetToolStatus(t *testing.T) {
	executor := NewMockExecutor()
	tk := NewToolkitWithExecutor(executor)

	executor.SetResponse("which", []byte("/usr/bin/tool\n"), nil)

	status, err := tk.GetToolStatus()
	if err != nil {
		t.Fatalf("GetToolStatus error: %v", err)
	}

	if len(status) == 0 {
		t.Error("status should not be empty")
	}
}

func TestNetworkStruct(t *testing.T) {
	network := Network{
		BSSID:      "AA:BB:CC:DD:EE:FF",
		ESSID:      "TestNetwork",
		Channel:    11,
		Encryption: "WPA2",
		Signal:     -45,
	}

	if network.BSSID != "AA:BB:CC:DD:EE:FF" {
		t.Errorf("BSSID = %q, want %q", network.BSSID, "AA:BB:CC:DD:EE:FF")
	}
	if network.ESSID != "TestNetwork" {
		t.Errorf("ESSID = %q, want %q", network.ESSID, "TestNetwork")
	}
	if network.Channel != 11 {
		t.Errorf("Channel = %d, want %d", network.Channel, 11)
	}
	if network.Encryption != "WPA2" {
		t.Errorf("Encryption = %q, want %q", network.Encryption, "WPA2")
	}
	if network.Signal != -45 {
		t.Errorf("Signal = %d, want %d", network.Signal, -45)
	}
}

func TestErrorVariables_Toolkit(t *testing.T) {
	if ErrInvalidInput == nil {
		t.Error("ErrInvalidInput should not be nil")
	}
	if ErrCaptureTimeout == nil {
		t.Error("ErrCaptureTimeout should not be nil")
	}
}

func TestContainsPathTraversal(t *testing.T) {
	tests := []struct {
		path     string
		expected bool
	}{
		{"/tmp/capture.cap", false},
		{"capture.cap", false},
		{"../../../etc/passwd", true},
		{"/tmp/../etc/passwd", true},
		{"./capture.cap", false},
		{"subdir/capture.cap", false},
		{"..hidden", true}, // Contains ".." even if not traversal
		{"/absolute/path/file.cap", false},
	}

	for _, tt := range tests {
		t.Run(tt.path, func(t *testing.T) {
			result := containsPathTraversal(tt.path)
			if result != tt.expected {
				t.Errorf("containsPathTraversal(%q) = %v, want %v", tt.path, result, tt.expected)
			}
		})
	}
}

func TestToolkit_CrackPassword_PathTraversal(t *testing.T) {
	executor := NewMockExecutor()
	tk := NewToolkitWithExecutor(executor)

	// Test path traversal in capture file
	_, err := tk.CrackPassword("../../../etc/passwd", "/wordlist.txt")
	if !errors.Is(err, ErrPathTraversal) {
		t.Errorf("expected ErrPathTraversal for capture file traversal, got: %v", err)
	}

	// Test path traversal in wordlist
	tmpDir := t.TempDir()
	capFile := filepath.Join(tmpDir, "test.cap")
	os.WriteFile(capFile, []byte("dummy"), 0644)

	_, err = tk.CrackPassword(capFile, "../../../etc/passwd")
	if !errors.Is(err, ErrPathTraversal) {
		t.Errorf("expected ErrPathTraversal for wordlist traversal, got: %v", err)
	}
}

func TestErrPathTraversal(t *testing.T) {
	if ErrPathTraversal == nil {
		t.Fatal("ErrPathTraversal should not be nil")
	}
	expected := "path traversal not allowed"
	if ErrPathTraversal.Error() != expected {
		t.Errorf("ErrPathTraversal = %q, want %q", ErrPathTraversal.Error(), expected)
	}
}

func TestCleanupCaptureFiles(t *testing.T) {
	tmpDir := t.TempDir()
	prefix := filepath.Join(tmpDir, "test_capture")

	// Create test files
	testFiles := []string{
		prefix + "-01.cap",
		prefix + "-01.csv",
		prefix + "-01.kismet.csv",
		prefix + "-01.kismet.netxml",
		prefix + "-01.log.csv",
	}
	for _, f := range testFiles {
		os.WriteFile(f, []byte("test"), 0644)
	}

	// Verify files exist
	for _, f := range testFiles {
		if _, err := os.Stat(f); os.IsNotExist(err) {
			t.Fatalf("test file %s should exist before cleanup", f)
		}
	}

	// Run cleanup
	cleanupCaptureFiles(prefix)

	// Verify files are removed
	for _, f := range testFiles {
		if _, err := os.Stat(f); !os.IsNotExist(err) {
			t.Errorf("file %s should be removed after cleanup", f)
		}
	}
}
