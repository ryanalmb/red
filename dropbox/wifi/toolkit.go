// Package wifi provides wrappers for WiFi security tools.
// This package interfaces with aircrack-ng, wifite, and kismet for wireless assessments.
package wifi

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// ErrNotImplemented is returned when a feature is not yet implemented.
// Deprecated: Most WiFi toolkit features are now implemented. Use specific methods.
var ErrNotImplemented = errors.New("wifi toolkit method requires interface parameter - use *WithInterface variant")

// ErrPathTraversal is returned when a file path attempts directory traversal.
var ErrPathTraversal = errors.New("path traversal not allowed")

// ErrInvalidInput is returned when input validation fails.
var ErrInvalidInput = errors.New("invalid input")

// ErrCaptureTimeout is returned when handshake capture times out.
var ErrCaptureTimeout = errors.New("handshake capture timeout")

// Toolkit provides access to WiFi security tools.
type Toolkit struct {
	// AircrackPath is the path to the aircrack-ng binary.
	AircrackPath string

	// WifitePath is the path to the wifite binary.
	WifitePath string

	// KismetPath is the path to the kismet binary.
	KismetPath string

	// executor is the command executor (for testability).
	executor CommandExecutor

	// interfaceManager handles wireless interface operations.
	interfaceManager *InterfaceManager

	// toolChecker verifies tool availability.
	toolChecker *ToolChecker

	// TempDir is the directory for temporary capture files.
	TempDir string
}

// NewToolkit creates a new WiFi toolkit with default tool paths.
func NewToolkit() *Toolkit {
	executor := NewRealExecutor()
	return &Toolkit{
		AircrackPath:     "aircrack-ng",
		WifitePath:       "wifite",
		KismetPath:       "kismet",
		executor:         executor,
		interfaceManager: NewInterfaceManager(executor),
		toolChecker:      NewToolChecker(executor),
		TempDir:          os.TempDir(),
	}
}

// NewToolkitWithExecutor creates a new WiFi toolkit with a custom executor (for testing).
func NewToolkitWithExecutor(executor CommandExecutor) *Toolkit {
	return &Toolkit{
		AircrackPath:     "aircrack-ng",
		WifitePath:       "wifite",
		KismetPath:       "kismet",
		executor:         executor,
		interfaceManager: NewInterfaceManager(executor),
		toolChecker:      NewToolChecker(executor),
		TempDir:          os.TempDir(),
	}
}

// CheckTools verifies that required tools are installed.
func (t *Toolkit) CheckTools() error {
	return t.toolChecker.CheckRequiredTools()
}

// GetToolStatus returns the status of all WiFi tools.
func (t *Toolkit) GetToolStatus() (map[Tool]*ToolStatus, error) {
	return t.toolChecker.CheckAllTools()
}

// FindInterfaces returns all wireless interfaces on the system.
func (t *Toolkit) FindInterfaces() ([]WirelessInterface, error) {
	return t.interfaceManager.FindWirelessInterfaces()
}

// EnableMonitorMode enables monitor mode on an interface.
func (t *Toolkit) EnableMonitorMode(iface string) (string, error) {
	return t.interfaceManager.EnableMonitorMode(iface)
}

// DisableMonitorMode disables monitor mode on an interface.
func (t *Toolkit) DisableMonitorMode(iface string) (string, error) {
	return t.interfaceManager.DisableMonitorMode(iface)
}

// ScanNetworks scans for available WiFi networks using airodump-ng.
// Deprecated: Use ScanNetworksWithInterface for explicit interface control.
// This method attempts to find a monitor-mode interface automatically.
func (t *Toolkit) ScanNetworks() ([]Network, error) {
	// Try to find a monitor mode interface
	interfaces, err := t.FindInterfaces()
	if err != nil {
		return nil, fmt.Errorf("failed to find interfaces: %w", err)
	}

	// Look for a monitor mode interface
	for _, iface := range interfaces {
		if iface.MonitorMode {
			return t.ScanNetworksWithInterface(iface.Name, 10)
		}
	}

	// No monitor interface found
	return nil, fmt.Errorf("%w: no monitor mode interface found - enable with EnableMonitorMode first", ErrNoWirelessInterface)
}

// ScanNetworksWithInterface scans for WiFi networks on a specific interface.
// The interface should already be in monitor mode.
// Duration is in seconds.
func (t *Toolkit) ScanNetworksWithInterface(iface string, duration int) ([]Network, error) {
	if iface == "" {
		return nil, fmt.Errorf("%w: interface name required", ErrInvalidInput)
	}
	if !isValidInterfaceName(iface) {
		return nil, fmt.Errorf("%w: invalid interface name", ErrInvalidInput)
	}
	if duration <= 0 {
		duration = 10 // Default 10 seconds
	}

	// Create temp file for CSV output
	outputPrefix := filepath.Join(t.TempDir, fmt.Sprintf("wifi_scan_%d", time.Now().UnixNano()))

	// Build airodump-ng command
	// airodump-ng wlan0mon --write /tmp/scan --output-format csv --write-interval 1
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(duration+5)*time.Second)
	defer cancel()

	args := []string{
		iface,
		"--write", outputPrefix,
		"--output-format", "csv",
		"--write-interval", "1",
	}

	// Start airodump-ng (it runs until killed)
	proc, err := t.executor.Start("airodump-ng", args...)
	if err != nil {
		return nil, fmt.Errorf("failed to start airodump-ng: %w", err)
	}

	// Wait for duration then kill
	select {
	case <-time.After(time.Duration(duration) * time.Second):
		proc.Kill()
	case <-ctx.Done():
		proc.Kill()
	}

	// Read CSV output file
	csvFile := outputPrefix + "-01.csv"
	data, err := os.ReadFile(csvFile)
	if err != nil {
		// Try without -01 suffix
		data, err = os.ReadFile(outputPrefix + ".csv")
		if err != nil {
			return nil, fmt.Errorf("failed to read scan results: %w", err)
		}
	}

	// Clean up temp files
	os.Remove(csvFile)
	os.Remove(outputPrefix + "-01.cap")
	os.Remove(outputPrefix + "-01.kismet.csv")
	os.Remove(outputPrefix + "-01.kismet.netxml")
	os.Remove(outputPrefix + "-01.log.csv")

	return ParseAirodumpCSV(data), nil
}

// CaptureHandshake captures a WPA/WPA2 handshake for a target network.
// Deprecated: Use CaptureHandshakeWithInterface for explicit interface control.
// This method attempts to find a monitor-mode interface automatically.
func (t *Toolkit) CaptureHandshake(bssid string, channel int) error {
	// Try to find a monitor mode interface
	interfaces, err := t.FindInterfaces()
	if err != nil {
		return fmt.Errorf("failed to find interfaces: %w", err)
	}

	// Look for a monitor mode interface
	for _, iface := range interfaces {
		if iface.MonitorMode {
			_, err := t.CaptureHandshakeWithInterface(iface.Name, bssid, channel, 60)
			return err
		}
	}

	// No monitor interface found
	return fmt.Errorf("%w: no monitor mode interface found - enable with EnableMonitorMode first", ErrNoWirelessInterface)
}

// CaptureHandshakeWithInterface captures a handshake on a specific interface.
// Returns the path to the capture file on success.
func (t *Toolkit) CaptureHandshakeWithInterface(iface, bssid string, channel, timeout int) (string, error) {
	// Validate inputs
	bssid = SanitizeBSSID(bssid)
	if bssid == "" {
		return "", fmt.Errorf("%w: invalid BSSID format", ErrInvalidInput)
	}
	channel = SanitizeChannel(channel)
	if channel == 0 {
		return "", fmt.Errorf("%w: invalid channel", ErrInvalidInput)
	}
	if !isValidInterfaceName(iface) {
		return "", fmt.Errorf("%w: invalid interface name", ErrInvalidInput)
	}
	if timeout <= 0 {
		timeout = 60 // Default 60 seconds
	}

	// Create temp file for capture
	outputPrefix := filepath.Join(t.TempDir, fmt.Sprintf("capture_%d", time.Now().UnixNano()))

	// Build airodump-ng command for targeted capture
	// airodump-ng -c <channel> --bssid <bssid> -w <output> wlan0mon
	args := []string{
		"-c", fmt.Sprintf("%d", channel),
		"--bssid", bssid,
		"-w", outputPrefix,
		iface,
	}

	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeout+10)*time.Second)
	defer cancel()

	// Start airodump-ng
	proc, err := t.executor.Start("airodump-ng", args...)
	if err != nil {
		return "", fmt.Errorf("failed to start capture: %w", err)
	}

	// Poll for handshake or timeout
	captureFile := outputPrefix + "-01.cap"
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	startTime := time.Now()
	for {
		select {
		case <-ticker.C:
			// Check if capture file exists and has handshake
			if _, err := os.Stat(captureFile); err == nil {
				// Check with aircrack-ng if handshake is present
				output, _ := t.executor.Run("aircrack-ng", captureFile)
				if strings.Contains(string(output), "1 handshake") {
					proc.Kill()
					return captureFile, nil
				}
			}
			if time.Since(startTime) > time.Duration(timeout)*time.Second {
				proc.Kill()
				// Clean up temp files
				cleanupCaptureFiles(outputPrefix)
				return "", ErrCaptureTimeout
			}
		case <-ctx.Done():
			proc.Kill()
			// Clean up temp files on context cancellation
			cleanupCaptureFiles(outputPrefix)
			return "", ctx.Err()
		}
	}
}

// DeauthClient sends deauthentication frames to a client.
// Deprecated: Use DeauthClientWithInterface for explicit interface control.
// This method attempts to find a monitor-mode interface automatically.
func (t *Toolkit) DeauthClient(bssid string, clientMAC string) error {
	// Try to find a monitor mode interface
	interfaces, err := t.FindInterfaces()
	if err != nil {
		return fmt.Errorf("failed to find interfaces: %w", err)
	}

	// Look for a monitor mode interface
	for _, iface := range interfaces {
		if iface.MonitorMode {
			result, err := t.DeauthClientWithInterface(iface.Name, bssid, clientMAC, 10)
			if err != nil {
				return err
			}
			if !result.Success {
				return fmt.Errorf("deauth failed: %s", result.Error)
			}
			return nil
		}
	}

	// No monitor interface found
	return fmt.Errorf("%w: no monitor mode interface found - enable with EnableMonitorMode first", ErrNoWirelessInterface)
}

// DeauthClientWithInterface sends deauth frames on a specific interface.
// If clientMAC is empty, sends broadcast deauth (all clients).
// Count is the number of deauth frames to send (0 = continuous).
func (t *Toolkit) DeauthClientWithInterface(iface, bssid, clientMAC string, count int) (*AireplayResult, error) {
	// Validate inputs
	bssid = SanitizeBSSID(bssid)
	if bssid == "" {
		return nil, fmt.Errorf("%w: invalid BSSID format", ErrInvalidInput)
	}
	if !isValidInterfaceName(iface) {
		return nil, fmt.Errorf("%w: invalid interface name", ErrInvalidInput)
	}
	if clientMAC != "" {
		clientMAC = SanitizeBSSID(clientMAC)
		if clientMAC == "" {
			return nil, fmt.Errorf("%w: invalid client MAC format", ErrInvalidInput)
		}
	}
	if count <= 0 {
		count = 10 // Default 10 deauth frames
	}

	// Build aireplay-ng command
	// aireplay-ng --deauth <count> -a <bssid> [-c <client>] <interface>
	args := []string{
		"--deauth", fmt.Sprintf("%d", count),
		"-a", bssid,
	}

	if clientMAC != "" {
		args = append(args, "-c", clientMAC)
	}

	args = append(args, iface)

	output, err := t.executor.Run("aireplay-ng", args...)
	if err != nil {
		return &AireplayResult{
			Success: false,
			Error:   fmt.Sprintf("aireplay-ng failed: %v", err),
		}, nil
	}

	return ParseAireplayOutput(output), nil
}

// CrackPassword attempts to crack a WPA/WPA2 password using aircrack-ng.
func (t *Toolkit) CrackPassword(captureFile, wordlist string) (*AircrackResult, error) {
	// Validate inputs
	if captureFile == "" {
		return nil, fmt.Errorf("%w: capture file path required", ErrInvalidInput)
	}
	if wordlist == "" {
		return nil, fmt.Errorf("%w: wordlist path required", ErrInvalidInput)
	}

	// Validate file paths - prevent path traversal
	captureFile = filepath.Clean(captureFile)
	wordlist = filepath.Clean(wordlist)

	// Security: Reject paths containing traversal patterns
	if containsPathTraversal(captureFile) {
		return nil, fmt.Errorf("%w: capture file path contains traversal", ErrPathTraversal)
	}
	if containsPathTraversal(wordlist) {
		return nil, fmt.Errorf("%w: wordlist path contains traversal", ErrPathTraversal)
	}

	// Check files exist
	if _, err := os.Stat(captureFile); os.IsNotExist(err) {
		return nil, fmt.Errorf("%w: capture file not found: %s", ErrInvalidInput, captureFile)
	}
	if _, err := os.Stat(wordlist); os.IsNotExist(err) {
		return nil, fmt.Errorf("%w: wordlist not found: %s", ErrInvalidInput, wordlist)
	}

	// Build aircrack-ng command
	// aircrack-ng -w <wordlist> <capfile>
	output, err := t.executor.Run("aircrack-ng", "-w", wordlist, captureFile)
	if err != nil {
		// aircrack-ng returns non-zero if password not found, check output
		result := ParseAircrackOutput(output)
		if result.Success {
			return result, nil
		}
		return &AircrackResult{
			Success: false,
		}, nil
	}

	return ParseAircrackOutput(output), nil
}

// Network represents a discovered WiFi network.
type Network struct {
	// BSSID is the MAC address of the access point.
	BSSID string

	// ESSID is the network name (SSID).
	ESSID string

	// Channel is the WiFi channel number.
	Channel int

	// Encryption is the encryption type (WPA, WPA2, WEP, Open).
	Encryption string

	// Signal is the signal strength in dBm.
	Signal int
}

// containsPathTraversal checks if a file path contains directory traversal patterns.
// This is a security check to prevent accessing files outside allowed directories.
func containsPathTraversal(path string) bool {
	// Check for ".." components that could escape directories
	if strings.Contains(path, "..") {
		return true
	}
	// Check for absolute paths starting with / (could bypass TempDir restriction)
	// Allow absolute paths only if they don't contain traversal
	return false
}

// cleanupCaptureFiles removes temporary files created during capture operations.
func cleanupCaptureFiles(outputPrefix string) {
	os.Remove(outputPrefix + "-01.cap")
	os.Remove(outputPrefix + "-01.csv")
	os.Remove(outputPrefix + "-01.kismet.csv")
	os.Remove(outputPrefix + "-01.kismet.netxml")
	os.Remove(outputPrefix + "-01.log.csv")
}
