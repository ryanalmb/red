// Package wifi provides wrappers for WiFi security tools.
package wifi

import (
	"bufio"
	"bytes"
	"regexp"
	"strconv"
	"strings"
)

// ParseAirodumpCSV parses airodump-ng CSV output into Network structs.
// CSV format:
// BSSID, First time seen, Last time seen, channel, Speed, Privacy, Cipher, Authentication, Power, # beacons, # IV, LAN IP, ID-length, ESSID, Key
func ParseAirodumpCSV(data []byte) []Network {
	networks := make([]Network, 0)
	scanner := bufio.NewScanner(bytes.NewReader(data))

	// Skip until we find the header line
	inNetworkSection := false
	inClientSection := false

	for scanner.Scan() {
		line := scanner.Text()

		// Check for section markers
		if strings.HasPrefix(line, "BSSID,") {
			inNetworkSection = true
			inClientSection = false
			continue
		}
		if strings.HasPrefix(line, "Station MAC,") {
			inNetworkSection = false
			inClientSection = true
			continue
		}

		// Skip empty lines and client section
		if line == "" || inClientSection || !inNetworkSection {
			continue
		}

		// Parse network line
		network := parseAirodumpNetworkLine(line)
		if network != nil {
			networks = append(networks, *network)
		}
	}

	return networks
}

// parseAirodumpNetworkLine parses a single line of airodump CSV output.
func parseAirodumpNetworkLine(line string) *Network {
	// Split by comma, but be careful with ESSID which might contain commas
	parts := strings.Split(line, ",")
	if len(parts) < 14 {
		return nil
	}

	// Trim whitespace from all parts
	for i := range parts {
		parts[i] = strings.TrimSpace(parts[i])
	}

	bssid := parts[0]
	if !isValidMAC(bssid) {
		return nil
	}

	channel, _ := strconv.Atoi(parts[3])
	power, _ := strconv.Atoi(parts[8])

	// ESSID is at index 13, but might contain commas
	// Join remaining parts after index 12 as ESSID
	essid := parts[13]
	if len(parts) > 14 {
		essid = strings.Join(parts[13:len(parts)-1], ",")
	}
	essid = strings.TrimSpace(essid)

	// Parse encryption from Privacy field (index 5)
	encryption := normalizeEncryption(parts[5])

	return &Network{
		BSSID:      bssid,
		ESSID:      essid,
		Channel:    channel,
		Encryption: encryption,
		Signal:     power,
	}
}

// normalizeEncryption normalizes encryption type string.
func normalizeEncryption(privacy string) string {
	privacy = strings.ToUpper(strings.TrimSpace(privacy))

	switch {
	case strings.Contains(privacy, "WPA3"):
		return "WPA3"
	case strings.Contains(privacy, "WPA2"):
		return "WPA2"
	case strings.Contains(privacy, "WPA"):
		return "WPA"
	case strings.Contains(privacy, "WEP"):
		return "WEP"
	case strings.Contains(privacy, "OPN") || privacy == "":
		return "Open"
	default:
		return privacy
	}
}

// isValidMAC validates MAC address format.
func isValidMAC(mac string) bool {
	// MAC format: XX:XX:XX:XX:XX:XX (case insensitive)
	matched, _ := regexp.MatchString(`^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$`, mac)
	return matched
}

// IsValidBSSID validates a BSSID (MAC address) format.
// Exported for use by other packages.
func IsValidBSSID(bssid string) bool {
	return isValidMAC(bssid)
}

// AircrackResult represents the result of an aircrack-ng password crack.
type AircrackResult struct {
	Success  bool
	Password string
	BSSID    string
	ESSID    string
}

// ParseAircrackOutput parses aircrack-ng output to extract cracked password.
// Looks for "KEY FOUND! [ password ]" pattern.
func ParseAircrackOutput(data []byte) *AircrackResult {
	result := &AircrackResult{
		Success: false,
	}

	content := string(data)

	// Look for "KEY FOUND!"
	keyFoundRegex := regexp.MustCompile(`KEY FOUND!\s*\[\s*([^\]]+)\s*\]`)
	if matches := keyFoundRegex.FindStringSubmatch(content); matches != nil {
		result.Success = true
		result.Password = strings.TrimSpace(matches[1])
	}

	// Extract BSSID if present
	bssidRegex := regexp.MustCompile(`([0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2})`)
	if matches := bssidRegex.FindStringSubmatch(content); matches != nil {
		result.BSSID = matches[1]
	}

	// Extract ESSID if present
	essidRegex := regexp.MustCompile(`ESSID:\s*"?([^"\n]+)"?`)
	if matches := essidRegex.FindStringSubmatch(content); matches != nil {
		result.ESSID = strings.TrimSpace(matches[1])
	}

	return result
}

// AireplayResult represents the result of an aireplay-ng operation.
type AireplayResult struct {
	Success      bool
	PacketsSent  int
	ACKsReceived int
	Error        string
}

// ParseAireplayOutput parses aireplay-ng deauth output.
func ParseAireplayOutput(data []byte) *AireplayResult {
	result := &AireplayResult{
		Success: false,
	}

	content := string(data)

	// Look for deauth packet counts
	// Example: "Sending 64 directed DeAuth (code 7). STMAC: [AA:BB:CC:DD:EE:FF] [ 5|64 ACKs]"
	sentRegex := regexp.MustCompile(`Sending\s+(\d+)\s+`)
	if matches := sentRegex.FindStringSubmatch(content); matches != nil {
		result.PacketsSent, _ = strconv.Atoi(matches[1])
		result.Success = result.PacketsSent > 0
	}

	// Look for ACK count
	ackRegex := regexp.MustCompile(`(\d+)\|?\d*\s*ACKs?\]`)
	if matches := ackRegex.FindStringSubmatch(content); matches != nil {
		result.ACKsReceived, _ = strconv.Atoi(matches[1])
	}

	// Check for errors
	if strings.Contains(content, "No such BSSID") {
		result.Success = false
		result.Error = "target BSSID not found"
	}
	if strings.Contains(content, "wi_write") && strings.Contains(content, "failed") {
		result.Success = false
		result.Error = "injection failed - check interface"
	}

	return result
}

// CaptureStatus represents the status of a handshake capture.
type CaptureStatus struct {
	HandshakeCaptured bool
	CaptureFile       string
	BSSID             string
	Channel           int
	PacketCount       int
}

// ParseCaptureStatus parses airodump-ng capture status output.
// Looks for "WPA handshake: XX:XX:XX:XX:XX:XX" in output.
func ParseCaptureStatus(data []byte, captureFile string) *CaptureStatus {
	status := &CaptureStatus{
		HandshakeCaptured: false,
		CaptureFile:       captureFile,
	}

	content := string(data)

	// Look for handshake capture indication
	handshakeRegex := regexp.MustCompile(`WPA handshake:\s*([0-9A-Fa-f:]+)`)
	if matches := handshakeRegex.FindStringSubmatch(content); matches != nil {
		status.HandshakeCaptured = true
		status.BSSID = matches[1]
	}

	// Extract channel
	channelRegex := regexp.MustCompile(`CH\s*(\d+)`)
	if matches := channelRegex.FindStringSubmatch(content); matches != nil {
		status.Channel, _ = strconv.Atoi(matches[1])
	}

	return status
}

// SanitizeBSSID validates and normalizes a BSSID string.
// Returns empty string if invalid.
func SanitizeBSSID(bssid string) string {
	bssid = strings.TrimSpace(strings.ToUpper(bssid))
	if !isValidMAC(bssid) {
		return ""
	}
	return bssid
}

// SanitizeChannel validates a WiFi channel number.
// Returns 0 if invalid.
func SanitizeChannel(channel int) int {
	// 2.4GHz channels: 1-14
	// 5GHz channels: 36-165 (varies by region)
	if (channel >= 1 && channel <= 14) || (channel >= 36 && channel <= 165) {
		return channel
	}
	return 0
}
