package wifi

import (
	"testing"
)

func TestParseAirodumpCSV(t *testing.T) {
	// Sample airodump CSV output
	csvData := `
BSSID, First time seen, Last time seen, channel, Speed, Privacy, Cipher, Authentication, Power, # beacons, # IV, LAN IP, ID-length, ESSID, Key

AA:BB:CC:DD:EE:FF, 2024-01-01 12:00:00, 2024-01-01 12:00:30, 6, 54, WPA2, CCMP, PSK, -45, 100, 0, 0.0.0.0, 8, TestNetwork,
11:22:33:44:55:66, 2024-01-01 12:00:05, 2024-01-01 12:00:30, 11, 54, WPA, TKIP, PSK, -60, 50, 0, 0.0.0.0, 10, AnotherNet,
DE:AD:BE:EF:CA:FE, 2024-01-01 12:00:10, 2024-01-01 12:00:30, 1, 54, OPN, , , -70, 20, 0, 0.0.0.0, 4, Open,

Station MAC, First time seen, Last time seen, Power, # packets, BSSID, Probed ESSIDs

FF:FF:FF:FF:FF:01, 2024-01-01 12:00:00, 2024-01-01 12:00:30, -50, 100, AA:BB:CC:DD:EE:FF,
`

	networks := ParseAirodumpCSV([]byte(csvData))

	if len(networks) != 3 {
		t.Fatalf("len(networks) = %d, want 3", len(networks))
	}

	// Check first network
	if networks[0].BSSID != "AA:BB:CC:DD:EE:FF" {
		t.Errorf("networks[0].BSSID = %q, want %q", networks[0].BSSID, "AA:BB:CC:DD:EE:FF")
	}
	if networks[0].ESSID != "TestNetwork" {
		t.Errorf("networks[0].ESSID = %q, want %q", networks[0].ESSID, "TestNetwork")
	}
	if networks[0].Channel != 6 {
		t.Errorf("networks[0].Channel = %d, want 6", networks[0].Channel)
	}
	if networks[0].Encryption != "WPA2" {
		t.Errorf("networks[0].Encryption = %q, want %q", networks[0].Encryption, "WPA2")
	}
	if networks[0].Signal != -45 {
		t.Errorf("networks[0].Signal = %d, want -45", networks[0].Signal)
	}

	// Check second network
	if networks[1].Encryption != "WPA" {
		t.Errorf("networks[1].Encryption = %q, want %q", networks[1].Encryption, "WPA")
	}

	// Check open network
	if networks[2].Encryption != "Open" {
		t.Errorf("networks[2].Encryption = %q, want %q", networks[2].Encryption, "Open")
	}
}

func TestParseAirodumpCSV_Empty(t *testing.T) {
	networks := ParseAirodumpCSV([]byte(""))
	if len(networks) != 0 {
		t.Errorf("len(networks) = %d, want 0 for empty input", len(networks))
	}
}

func TestParseAirodumpCSV_HeaderOnly(t *testing.T) {
	csvData := `BSSID, First time seen, Last time seen, channel, Speed, Privacy, Cipher, Authentication, Power, # beacons, # IV, LAN IP, ID-length, ESSID, Key
`
	networks := ParseAirodumpCSV([]byte(csvData))
	if len(networks) != 0 {
		t.Errorf("len(networks) = %d, want 0 for header only", len(networks))
	}
}

func TestIsValidMAC(t *testing.T) {
	tests := []struct {
		mac  string
		want bool
	}{
		{"AA:BB:CC:DD:EE:FF", true},
		{"aa:bb:cc:dd:ee:ff", true},
		{"00:11:22:33:44:55", true},
		{"AA:BB:CC:DD:EE:F", false},    // Too short
		{"AA:BB:CC:DD:EE:FFF", false},  // Too long
		{"AA-BB-CC-DD-EE-FF", false},   // Wrong separator
		{"AABBCCDDEEFF", false},        // No separator
		{"GG:HH:II:JJ:KK:LL", false},   // Invalid hex
		{"", false},
	}

	for _, tt := range tests {
		t.Run(tt.mac, func(t *testing.T) {
			got := isValidMAC(tt.mac)
			if got != tt.want {
				t.Errorf("isValidMAC(%q) = %v, want %v", tt.mac, got, tt.want)
			}
		})
	}
}

func TestIsValidBSSID(t *testing.T) {
	// IsValidBSSID is just an exported wrapper for isValidMAC
	if !IsValidBSSID("AA:BB:CC:DD:EE:FF") {
		t.Error("IsValidBSSID should return true for valid BSSID")
	}
	if IsValidBSSID("invalid") {
		t.Error("IsValidBSSID should return false for invalid BSSID")
	}
}

func TestNormalizeEncryption(t *testing.T) {
	tests := []struct {
		input string
		want  string
	}{
		{"WPA2", "WPA2"},
		{"wpa2", "WPA2"},
		{"WPA2 CCMP", "WPA2"},
		{"WPA", "WPA"},
		{"WPA TKIP", "WPA"},
		{"WPA3", "WPA3"},
		{"WEP", "WEP"},
		{"OPN", "Open"},
		{"", "Open"},
		{"  WPA2  ", "WPA2"},
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			got := normalizeEncryption(tt.input)
			if got != tt.want {
				t.Errorf("normalizeEncryption(%q) = %q, want %q", tt.input, got, tt.want)
			}
		})
	}
}

func TestParseAircrackOutput_KeyFound(t *testing.T) {
	output := `
                                 Aircrack-ng 1.7

      [00:00:01] 1234/5678 keys tested (1234.56 k/s)

      Time left: 0 seconds

                         KEY FOUND! [ mysecretpassword ]

      Master Key     : AA BB CC DD EE FF 00 11 22 33 44 55 66 77 88 99
                       AA BB CC DD EE FF 00 11 22 33 44 55 66 77 88 99
`

	result := ParseAircrackOutput([]byte(output))

	if !result.Success {
		t.Error("result.Success should be true")
	}
	if result.Password != "mysecretpassword" {
		t.Errorf("result.Password = %q, want %q", result.Password, "mysecretpassword")
	}
}

func TestParseAircrackOutput_KeyNotFound(t *testing.T) {
	output := `
                                 Aircrack-ng 1.7

      [00:05:00] 1000000/1000000 keys tested (3333.33 k/s)

      Time left: 0 seconds

                         Passphrase not in dictionary

`

	result := ParseAircrackOutput([]byte(output))

	if result.Success {
		t.Error("result.Success should be false")
	}
	if result.Password != "" {
		t.Errorf("result.Password should be empty, got %q", result.Password)
	}
}

func TestParseAircrackOutput_WithBSSID(t *testing.T) {
	output := `
Opening test.cap
Read 1234 packets.

   #  BSSID              ESSID                     Encryption

   1  AA:BB:CC:DD:EE:FF  TestNetwork               WPA (1 handshake)

KEY FOUND! [ password123 ]
`

	result := ParseAircrackOutput([]byte(output))

	if result.BSSID != "AA:BB:CC:DD:EE:FF" {
		t.Errorf("result.BSSID = %q, want %q", result.BSSID, "AA:BB:CC:DD:EE:FF")
	}
}

func TestParseAireplayOutput_Success(t *testing.T) {
	output := `12:34:56  Waiting for beacon frame (BSSID: AA:BB:CC:DD:EE:FF) on channel 6
12:34:57  Sending 64 directed DeAuth (code 7). STMAC: [11:22:33:44:55:66] [ 5|64 ACKs]
12:34:58  Sending 64 directed DeAuth (code 7). STMAC: [11:22:33:44:55:66] [12|64 ACKs]
`

	result := ParseAireplayOutput([]byte(output))

	if !result.Success {
		t.Error("result.Success should be true")
	}
	if result.PacketsSent != 64 {
		t.Errorf("result.PacketsSent = %d, want 64", result.PacketsSent)
	}
}

func TestParseAireplayOutput_BSSIDNotFound(t *testing.T) {
	output := `12:34:56  Waiting for beacon frame (BSSID: AA:BB:CC:DD:EE:FF) on channel 6
No such BSSID available.
`

	result := ParseAireplayOutput([]byte(output))

	if result.Success {
		t.Error("result.Success should be false")
	}
	if result.Error != "target BSSID not found" {
		t.Errorf("result.Error = %q, want %q", result.Error, "target BSSID not found")
	}
}

func TestParseCaptureStatus_HandshakeCaptured(t *testing.T) {
	output := `CH  6 ][ Elapsed: 30 s ][ 2024-01-01 12:00 ][ WPA handshake: AA:BB:CC:DD:EE:FF

 BSSID              PWR RXQ  Beacons    #Data, #/s  CH   MB   ENC CIPHER  AUTH ESSID

 AA:BB:CC:DD:EE:FF  -45 100      150       50    2   6   54   WPA2 CCMP   PSK  TestNetwork
`

	status := ParseCaptureStatus([]byte(output), "/tmp/capture-01.cap")

	if !status.HandshakeCaptured {
		t.Error("status.HandshakeCaptured should be true")
	}
	if status.BSSID != "AA:BB:CC:DD:EE:FF" {
		t.Errorf("status.BSSID = %q, want %q", status.BSSID, "AA:BB:CC:DD:EE:FF")
	}
	if status.Channel != 6 {
		t.Errorf("status.Channel = %d, want 6", status.Channel)
	}
	if status.CaptureFile != "/tmp/capture-01.cap" {
		t.Errorf("status.CaptureFile = %q, want %q", status.CaptureFile, "/tmp/capture-01.cap")
	}
}

func TestParseCaptureStatus_NoHandshake(t *testing.T) {
	output := `CH  6 ][ Elapsed: 30 s ][ 2024-01-01 12:00

 BSSID              PWR RXQ  Beacons    #Data, #/s  CH   MB   ENC CIPHER  AUTH ESSID

 AA:BB:CC:DD:EE:FF  -45 100      150        0    0   6   54   WPA2 CCMP   PSK  TestNetwork
`

	status := ParseCaptureStatus([]byte(output), "/tmp/capture-01.cap")

	if status.HandshakeCaptured {
		t.Error("status.HandshakeCaptured should be false")
	}
}

func TestSanitizeBSSID(t *testing.T) {
	tests := []struct {
		input string
		want  string
	}{
		{"AA:BB:CC:DD:EE:FF", "AA:BB:CC:DD:EE:FF"},
		{"aa:bb:cc:dd:ee:ff", "AA:BB:CC:DD:EE:FF"},
		{"  AA:BB:CC:DD:EE:FF  ", "AA:BB:CC:DD:EE:FF"},
		{"invalid", ""},
		{"", ""},
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			got := SanitizeBSSID(tt.input)
			if got != tt.want {
				t.Errorf("SanitizeBSSID(%q) = %q, want %q", tt.input, got, tt.want)
			}
		})
	}
}

func TestSanitizeChannel(t *testing.T) {
	tests := []struct {
		input int
		want  int
	}{
		{1, 1},
		{6, 6},
		{11, 11},
		{14, 14},
		{36, 36},
		{165, 165},
		{0, 0},
		{-1, 0},
		{15, 0},  // Invalid 2.4GHz
		{35, 0},  // Invalid 5GHz
		{200, 0}, // Out of range
	}

	for _, tt := range tests {
		t.Run("", func(t *testing.T) {
			got := SanitizeChannel(tt.input)
			if got != tt.want {
				t.Errorf("SanitizeChannel(%d) = %d, want %d", tt.input, got, tt.want)
			}
		})
	}
}

func TestAircrackResult_Struct(t *testing.T) {
	result := AircrackResult{
		Success:  true,
		Password: "test123",
		BSSID:    "AA:BB:CC:DD:EE:FF",
		ESSID:    "TestNetwork",
	}

	if !result.Success {
		t.Error("Success should be true")
	}
	if result.Password != "test123" {
		t.Errorf("Password = %q, want %q", result.Password, "test123")
	}
	if result.BSSID != "AA:BB:CC:DD:EE:FF" {
		t.Errorf("BSSID = %q, want %q", result.BSSID, "AA:BB:CC:DD:EE:FF")
	}
	if result.ESSID != "TestNetwork" {
		t.Errorf("ESSID = %q, want %q", result.ESSID, "TestNetwork")
	}
}

func TestAireplayResult_Struct(t *testing.T) {
	result := AireplayResult{
		Success:      true,
		PacketsSent:  64,
		ACKsReceived: 10,
		Error:        "",
	}

	if !result.Success {
		t.Error("Success should be true")
	}
	if result.PacketsSent != 64 {
		t.Errorf("PacketsSent = %d, want 64", result.PacketsSent)
	}
	if result.ACKsReceived != 10 {
		t.Errorf("ACKsReceived = %d, want 10", result.ACKsReceived)
	}
}
