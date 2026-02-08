// Package wifi provides wrappers for WiFi security tools.
package wifi

import (
	"bufio"
	"bytes"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

// Interface detection and monitor mode management errors.
var (
	// ErrNoWirelessInterface is returned when no wireless interface is found.
	ErrNoWirelessInterface = errors.New("no wireless interface found - ensure WiFi adapter is connected")

	// ErrInterfaceNotFound is returned when a specific interface doesn't exist.
	ErrInterfaceNotFound = errors.New("interface not found")

	// ErrNotWirelessInterface is returned when interface exists but is not wireless.
	ErrNotWirelessInterface = errors.New("interface is not a wireless interface")
)

// ErrMonitorModeFailed is returned when enabling/disabling monitor mode fails.
type ErrMonitorModeFailed struct {
	Interface string
	Reason    string
}

func (e *ErrMonitorModeFailed) Error() string {
	return fmt.Sprintf("monitor mode failed for %s: %s", e.Interface, e.Reason)
}

// WirelessInterface represents a wireless network interface.
type WirelessInterface struct {
	// Name is the interface name (e.g., "wlan0", "wlan0mon").
	Name string

	// Driver is the wireless driver name (e.g., "ath9k", "rtl8812au").
	Driver string

	// Chipset is the hardware chipset (if detectable).
	Chipset string

	// MonitorMode indicates if the interface is in monitor mode.
	MonitorMode bool

	// PHY is the physical device name (e.g., "phy0").
	PHY string
}

// InterfaceManager handles wireless interface detection and monitor mode.
type InterfaceManager struct {
	executor CommandExecutor
}

// NewInterfaceManager creates a new InterfaceManager with the given executor.
func NewInterfaceManager(executor CommandExecutor) *InterfaceManager {
	return &InterfaceManager{
		executor: executor,
	}
}

// FindWirelessInterfaces detects all wireless interfaces on the system.
// Uses /sys/class/net to find interfaces with wireless capabilities.
func (m *InterfaceManager) FindWirelessInterfaces() ([]WirelessInterface, error) {
	interfaces := make([]WirelessInterface, 0)

	// Method 1: Check /sys/class/net/*/wireless directory
	netPath := "/sys/class/net"
	entries, err := os.ReadDir(netPath)
	if err != nil {
		// Fall back to iw command if /sys not available
		return m.findWirelessInterfacesIW()
	}

	for _, entry := range entries {
		ifaceName := entry.Name()
		wirelessPath := filepath.Join(netPath, ifaceName, "wireless")

		// Check if wireless directory exists (indicates wireless interface)
		if _, err := os.Stat(wirelessPath); err == nil {
			iface := WirelessInterface{
				Name:        ifaceName,
				MonitorMode: strings.HasSuffix(ifaceName, "mon"),
			}

			// Try to get PHY info
			phyPath := filepath.Join(netPath, ifaceName, "phy80211", "name")
			if phyData, err := os.ReadFile(phyPath); err == nil {
				iface.PHY = strings.TrimSpace(string(phyData))
			}

			// Try to get driver info
			driverPath := filepath.Join(netPath, ifaceName, "device", "driver")
			if link, err := os.Readlink(driverPath); err == nil {
				iface.Driver = filepath.Base(link)
			}

			interfaces = append(interfaces, iface)
		}
	}

	// If no interfaces found via /sys, try iw command
	if len(interfaces) == 0 {
		return m.findWirelessInterfacesIW()
	}

	return interfaces, nil
}

// findWirelessInterfacesIW uses the 'iw' command to find wireless interfaces.
func (m *InterfaceManager) findWirelessInterfacesIW() ([]WirelessInterface, error) {
	output, err := m.executor.Run("iw", "dev")
	if err != nil {
		// If iw fails, try iwconfig as last resort
		return m.findWirelessInterfacesIWConfig()
	}

	return parseIWDevOutput(output), nil
}

// findWirelessInterfacesIWConfig uses the legacy 'iwconfig' command.
func (m *InterfaceManager) findWirelessInterfacesIWConfig() ([]WirelessInterface, error) {
	output, err := m.executor.Run("iwconfig")
	if err != nil {
		return nil, ErrNoWirelessInterface
	}

	return parseIWConfigOutput(output), nil
}

// parseIWDevOutput parses the output of 'iw dev' command.
// Example output:
//
//	phy#0
//	    Interface wlan0
//	        ifindex 3
//	        wdev 0x1
//	        addr 00:11:22:33:44:55
//	        type managed
func parseIWDevOutput(output []byte) []WirelessInterface {
	interfaces := make([]WirelessInterface, 0)
	scanner := bufio.NewScanner(bytes.NewReader(output))

	var currentPHY string
	var currentIface *WirelessInterface

	phyRegex := regexp.MustCompile(`^phy#(\d+)`)
	ifaceRegex := regexp.MustCompile(`^\s+Interface\s+(\S+)`)
	typeRegex := regexp.MustCompile(`^\s+type\s+(\S+)`)

	for scanner.Scan() {
		line := scanner.Text()

		if matches := phyRegex.FindStringSubmatch(line); matches != nil {
			currentPHY = "phy" + matches[1]
			continue
		}

		if matches := ifaceRegex.FindStringSubmatch(line); matches != nil {
			if currentIface != nil {
				interfaces = append(interfaces, *currentIface)
			}
			currentIface = &WirelessInterface{
				Name: matches[1],
				PHY:  currentPHY,
			}
			continue
		}

		if currentIface != nil {
			if matches := typeRegex.FindStringSubmatch(line); matches != nil {
				currentIface.MonitorMode = matches[1] == "monitor"
			}
		}
	}

	if currentIface != nil {
		interfaces = append(interfaces, *currentIface)
	}

	return interfaces
}

// parseIWConfigOutput parses the output of 'iwconfig' command.
// Example output:
//
//	wlan0     IEEE 802.11  ESSID:"NetworkName"
//	          Mode:Managed  Frequency:2.437 GHz  Access Point: 00:11:22:33:44:55
func parseIWConfigOutput(output []byte) []WirelessInterface {
	interfaces := make([]WirelessInterface, 0)
	scanner := bufio.NewScanner(bytes.NewReader(output))

	ifaceRegex := regexp.MustCompile(`^(\S+)\s+IEEE 802\.11`)
	modeRegex := regexp.MustCompile(`Mode:(\S+)`)

	var currentIface *WirelessInterface

	for scanner.Scan() {
		line := scanner.Text()

		if matches := ifaceRegex.FindStringSubmatch(line); matches != nil {
			if currentIface != nil {
				interfaces = append(interfaces, *currentIface)
			}
			currentIface = &WirelessInterface{
				Name: matches[1],
			}
		}

		if currentIface != nil {
			if matches := modeRegex.FindStringSubmatch(line); matches != nil {
				currentIface.MonitorMode = strings.ToLower(matches[1]) == "monitor"
			}
		}
	}

	if currentIface != nil {
		interfaces = append(interfaces, *currentIface)
	}

	return interfaces
}

// ValidateInterface checks if an interface exists and is a wireless interface.
func (m *InterfaceManager) ValidateInterface(iface string) error {
	if iface == "" {
		return ErrInterfaceNotFound
	}

	// Validate interface name format (alphanumeric only for security)
	if !isValidInterfaceName(iface) {
		return fmt.Errorf("%w: invalid interface name format", ErrInterfaceNotFound)
	}

	// Check if interface exists in /sys/class/net
	ifacePath := filepath.Join("/sys/class/net", iface)
	if _, err := os.Stat(ifacePath); os.IsNotExist(err) {
		return fmt.Errorf("%w: %s", ErrInterfaceNotFound, iface)
	}

	// Check if it's a wireless interface
	wirelessPath := filepath.Join(ifacePath, "wireless")
	if _, err := os.Stat(wirelessPath); os.IsNotExist(err) {
		return fmt.Errorf("%w: %s", ErrNotWirelessInterface, iface)
	}

	return nil
}

// isValidInterfaceName validates interface name format to prevent command injection.
// Only allows alphanumeric characters (e.g., wlan0, eth0, wlan0mon).
func isValidInterfaceName(name string) bool {
	if name == "" || len(name) > 15 { // Linux interface name limit
		return false
	}
	matched, _ := regexp.MatchString(`^[a-zA-Z][a-zA-Z0-9]*$`, name)
	return matched
}

// EnableMonitorMode enables monitor mode on a wireless interface using airmon-ng.
// Returns the name of the monitor interface (usually <iface>mon).
func (m *InterfaceManager) EnableMonitorMode(iface string) (string, error) {
	if err := m.ValidateInterface(iface); err != nil {
		return "", err
	}

	// Check if already in monitor mode
	if strings.HasSuffix(iface, "mon") {
		return iface, nil
	}

	// Run airmon-ng start <interface>
	output, err := m.executor.Run("airmon-ng", "start", iface)
	if err != nil {
		return "", &ErrMonitorModeFailed{
			Interface: iface,
			Reason:    fmt.Sprintf("airmon-ng failed: %v", err),
		}
	}

	// Parse output to find monitor interface name
	monIface := parseAirmonOutput(output, iface)
	if monIface == "" {
		// Default to <iface>mon if parsing fails
		monIface = iface + "mon"
	}

	return monIface, nil
}

// DisableMonitorMode disables monitor mode on a wireless interface using airmon-ng.
// Returns the name of the managed interface.
func (m *InterfaceManager) DisableMonitorMode(iface string) (string, error) {
	if iface == "" {
		return "", ErrInterfaceNotFound
	}

	// Validate interface name format
	if !isValidInterfaceName(iface) {
		return "", fmt.Errorf("%w: invalid interface name format", ErrInterfaceNotFound)
	}

	// Run airmon-ng stop <interface>
	output, err := m.executor.Run("airmon-ng", "stop", iface)
	if err != nil {
		return "", &ErrMonitorModeFailed{
			Interface: iface,
			Reason:    fmt.Sprintf("airmon-ng stop failed: %v", err),
		}
	}

	// Parse output to find managed interface name
	managedIface := parseAirmonStopOutput(output, iface)
	if managedIface == "" {
		// Default to removing "mon" suffix if present
		managedIface = strings.TrimSuffix(iface, "mon")
	}

	return managedIface, nil
}

// parseAirmonOutput parses airmon-ng start output to find monitor interface name.
// Example output:
//
//	PHY     Interface       Driver          Chipset
//	phy0    wlan0           ath9k_htc       Atheros Communications, Inc. AR9271
//	            (mac80211 monitor mode vif enabled for [phy0]wlan0 on [phy0]wlan0mon)
func parseAirmonOutput(output []byte, origIface string) string {
	// Look for pattern: "enabled for [phy0]wlan0 on [phy0]wlan0mon"
	// Capture the interface name after "on [phyX]"
	enabledRegex := regexp.MustCompile(`enabled.*on\s+\[\w+\](\w+)`)
	if matches := enabledRegex.FindSubmatch(output); matches != nil {
		return string(matches[1])
	}

	// Look for pattern: "monitor mode already enabled for [phy0]wlan0mon"
	// Capture the interface name after "[phyX]"
	alreadyRegex := regexp.MustCompile(`already enabled for \[\w+\](\w+)`)
	if matches := alreadyRegex.FindSubmatch(output); matches != nil {
		return string(matches[1])
	}

	return ""
}

// parseAirmonStopOutput parses airmon-ng stop output to find managed interface name.
func parseAirmonStopOutput(output []byte, origIface string) string {
	// Look for pattern: "disabled for [phy0]wlan0mon"
	// Capture the interface name after "[phyX]"
	disabledRegex := regexp.MustCompile(`disabled for \[\w+\](\w+)`)
	if matches := disabledRegex.FindSubmatch(output); matches != nil {
		result := string(matches[1])
		// Remove "mon" suffix to get managed interface name
		return strings.TrimSuffix(result, "mon")
	}

	return ""
}

// GetInterfaceInfo returns detailed information about a specific interface.
func (m *InterfaceManager) GetInterfaceInfo(iface string) (*WirelessInterface, error) {
	if err := m.ValidateInterface(iface); err != nil {
		return nil, err
	}

	info := &WirelessInterface{
		Name:        iface,
		MonitorMode: strings.HasSuffix(iface, "mon"),
	}

	// Get PHY info
	phyPath := filepath.Join("/sys/class/net", iface, "phy80211", "name")
	if phyData, err := os.ReadFile(phyPath); err == nil {
		info.PHY = strings.TrimSpace(string(phyData))
	}

	// Get driver info
	driverPath := filepath.Join("/sys/class/net", iface, "device", "driver")
	if link, err := os.Readlink(driverPath); err == nil {
		info.Driver = filepath.Base(link)
	}

	return info, nil
}
