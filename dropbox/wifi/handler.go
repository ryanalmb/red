// Package wifi provides wrappers for WiFi security tools.
package wifi

import (
	"encoding/json"
	"fmt"
)

// C2CommandType represents WiFi command types from C2 protocol.
type C2CommandType string

const (
	C2CommandWiFiScan       C2CommandType = "wifi_scan"
	C2CommandWiFiDeauth     C2CommandType = "wifi_deauth"
	C2CommandWiFiCapture    C2CommandType = "wifi_capture"
	C2CommandWiFiCrack      C2CommandType = "wifi_crack"
	C2CommandWiFiMonitorOn  C2CommandType = "wifi_monitor_on"
	C2CommandWiFiMonitorOff C2CommandType = "wifi_monitor_off"
)

// CommandHandler dispatches WiFi commands from C2 to the toolkit.
type CommandHandler struct {
	toolkit *Toolkit
}

// NewCommandHandler creates a new CommandHandler with the given toolkit.
func NewCommandHandler(toolkit *Toolkit) *CommandHandler {
	return &CommandHandler{
		toolkit: toolkit,
	}
}

// HandleCommand processes a WiFi command and returns a Result.
// Args is a map of command-specific arguments.
func (h *CommandHandler) HandleCommand(command string, args map[string]any) *Result {
	cmdType := C2CommandType(command)

	switch cmdType {
	case C2CommandWiFiScan:
		return h.handleScan(args)
	case C2CommandWiFiDeauth:
		return h.handleDeauth(args)
	case C2CommandWiFiCapture:
		return h.handleCapture(args)
	case C2CommandWiFiCrack:
		return h.handleCrack(args)
	case C2CommandWiFiMonitorOn:
		return h.handleMonitorOn(args)
	case C2CommandWiFiMonitorOff:
		return h.handleMonitorOff(args)
	default:
		return NewResult(false, "").WithError(fmt.Sprintf("unknown WiFi command: %s", command))
	}
}

// handleScan processes wifi_scan command.
// Args: interface (string), duration (int, optional)
func (h *CommandHandler) handleScan(args map[string]any) *Result {
	iface, ok := getStringArg(args, "interface")
	if !ok {
		return NewResult(false, "").WithError("missing required argument: interface")
	}

	duration := getIntArg(args, "duration", 10)

	networks, err := h.toolkit.ScanNetworksWithInterface(iface, duration)
	if err != nil {
		return NewResult(false, "").WithError(fmt.Sprintf("scan failed: %v", err))
	}

	// Convert networks to JSON-serializable format
	output := fmt.Sprintf("Found %d networks", len(networks))
	return NewResult(true, output).WithData(networks)
}

// handleDeauth processes wifi_deauth command.
// Args: interface (string), bssid (string), client_mac (string, optional), count (int, optional)
func (h *CommandHandler) handleDeauth(args map[string]any) *Result {
	iface, ok := getStringArg(args, "interface")
	if !ok {
		return NewResult(false, "").WithError("missing required argument: interface")
	}

	bssid, ok := getStringArg(args, "bssid")
	if !ok {
		return NewResult(false, "").WithError("missing required argument: bssid")
	}

	clientMAC, _ := getStringArg(args, "client_mac")
	count := getIntArg(args, "count", 10)

	result, err := h.toolkit.DeauthClientWithInterface(iface, bssid, clientMAC, count)
	if err != nil {
		return NewResult(false, "").WithError(fmt.Sprintf("deauth failed: %v", err))
	}

	if !result.Success {
		return NewResult(false, "").WithError(result.Error).WithData(result)
	}

	output := fmt.Sprintf("Sent %d deauth packets", result.PacketsSent)
	return NewResult(true, output).WithData(result)
}

// handleCapture processes wifi_capture command.
// Args: interface (string), bssid (string), channel (int), timeout (int, optional)
func (h *CommandHandler) handleCapture(args map[string]any) *Result {
	iface, ok := getStringArg(args, "interface")
	if !ok {
		return NewResult(false, "").WithError("missing required argument: interface")
	}

	bssid, ok := getStringArg(args, "bssid")
	if !ok {
		return NewResult(false, "").WithError("missing required argument: bssid")
	}

	channel := getIntArg(args, "channel", 0)
	if channel == 0 {
		return NewResult(false, "").WithError("missing required argument: channel")
	}

	timeout := getIntArg(args, "timeout", 60)

	captureFile, err := h.toolkit.CaptureHandshakeWithInterface(iface, bssid, channel, timeout)
	if err != nil {
		return NewResult(false, "").WithError(fmt.Sprintf("capture failed: %v", err))
	}

	output := fmt.Sprintf("Handshake captured: %s", captureFile)
	return NewResult(true, output).WithData(map[string]string{
		"capture_file": captureFile,
		"bssid":        bssid,
	})
}

// handleCrack processes wifi_crack command.
// Args: capture_file (string), wordlist (string)
func (h *CommandHandler) handleCrack(args map[string]any) *Result {
	captureFile, ok := getStringArg(args, "capture_file")
	if !ok {
		return NewResult(false, "").WithError("missing required argument: capture_file")
	}

	wordlist, ok := getStringArg(args, "wordlist")
	if !ok {
		return NewResult(false, "").WithError("missing required argument: wordlist")
	}

	result, err := h.toolkit.CrackPassword(captureFile, wordlist)
	if err != nil {
		return NewResult(false, "").WithError(fmt.Sprintf("crack failed: %v", err))
	}

	if !result.Success {
		return NewResult(false, "Password not found").WithData(result)
	}

	output := fmt.Sprintf("Password found: %s", result.Password)
	return NewResult(true, output).WithData(result)
}

// handleMonitorOn processes wifi_monitor_on command.
// Args: interface (string)
func (h *CommandHandler) handleMonitorOn(args map[string]any) *Result {
	iface, ok := getStringArg(args, "interface")
	if !ok {
		return NewResult(false, "").WithError("missing required argument: interface")
	}

	monIface, err := h.toolkit.EnableMonitorMode(iface)
	if err != nil {
		return NewResult(false, "").WithError(fmt.Sprintf("enable monitor mode failed: %v", err))
	}

	output := fmt.Sprintf("Monitor mode enabled: %s", monIface)
	return NewResult(true, output).WithData(map[string]string{
		"monitor_interface": monIface,
		"original_interface": iface,
	})
}

// handleMonitorOff processes wifi_monitor_off command.
// Args: interface (string)
func (h *CommandHandler) handleMonitorOff(args map[string]any) *Result {
	iface, ok := getStringArg(args, "interface")
	if !ok {
		return NewResult(false, "").WithError("missing required argument: interface")
	}

	managedIface, err := h.toolkit.DisableMonitorMode(iface)
	if err != nil {
		return NewResult(false, "").WithError(fmt.Sprintf("disable monitor mode failed: %v", err))
	}

	output := fmt.Sprintf("Monitor mode disabled: %s", managedIface)
	return NewResult(true, output).WithData(map[string]string{
		"managed_interface":  managedIface,
		"original_interface": iface,
	})
}

// Helper functions for argument extraction

// getStringArg extracts a string argument from the args map.
func getStringArg(args map[string]any, key string) (string, bool) {
	if args == nil {
		return "", false
	}
	val, ok := args[key]
	if !ok {
		return "", false
	}
	str, ok := val.(string)
	return str, ok
}

// getIntArg extracts an int argument from the args map with a default value.
func getIntArg(args map[string]any, key string, defaultVal int) int {
	if args == nil {
		return defaultVal
	}
	val, ok := args[key]
	if !ok {
		return defaultVal
	}

	// Handle different numeric types from JSON unmarshaling
	switch v := val.(type) {
	case int:
		return v
	case int64:
		return int(v)
	case float64:
		return int(v)
	case json.Number:
		if i, err := v.Int64(); err == nil {
			return int(i)
		}
	}

	return defaultVal
}

// IsWiFiCommand checks if a command string is a WiFi command.
func IsWiFiCommand(command string) bool {
	switch C2CommandType(command) {
	case C2CommandWiFiScan, C2CommandWiFiDeauth, C2CommandWiFiCapture,
		C2CommandWiFiCrack, C2CommandWiFiMonitorOn, C2CommandWiFiMonitorOff:
		return true
	default:
		return false
	}
}

// GetSupportedCommands returns a list of supported WiFi commands.
func GetSupportedCommands() []C2CommandType {
	return []C2CommandType{
		C2CommandWiFiScan,
		C2CommandWiFiDeauth,
		C2CommandWiFiCapture,
		C2CommandWiFiCrack,
		C2CommandWiFiMonitorOn,
		C2CommandWiFiMonitorOff,
	}
}
