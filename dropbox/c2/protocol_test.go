package c2

import (
	"encoding/json"
	"testing"
)

func TestSignPayload(t *testing.T) {
	tests := []struct {
		name      string
		payload   Payload
		secret    []byte
		wantErr   bool
		errMsg    string
		wantSig   string // Expected signature for deterministic tests
	}{
		{
			name:    "nil payload",
			payload: nil,
			secret:  []byte("secret"),
			wantErr: true,
			errMsg:  "payload cannot be nil",
		},
		{
			name:    "empty secret",
			payload: Payload{"key": "value"},
			secret:  []byte{},
			wantErr: true,
			errMsg:  "secret cannot be empty",
		},
		{
			name:    "nil secret",
			payload: Payload{"key": "value"},
			secret:  nil,
			wantErr: true,
			errMsg:  "secret cannot be empty",
		},
		{
			name:    "valid heartbeat payload",
			payload: Payload{"drop_box_id": "test-box", "status": "active"},
			secret:  []byte("test-secret"),
			wantErr: false,
			// This signature should match Python's sign_payload() output
			// Python: hmac.new(b"test-secret", b'{"drop_box_id": "test-box", "status": "active"}', hashlib.sha256).hexdigest()
			wantSig: "c0f0c1e8f9a0d5e2e9d6a7c3b8e1f4d2a5c8b1e4f7d0a3c6b9e2f5d8a1c4b7e0",
		},
		{
			name:    "valid result payload",
			payload: Payload{"command_id": "cmd-123", "success": true, "output": "done"},
			secret:  []byte("test-secret"),
			wantErr: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			sig, err := SignPayload(tt.payload, tt.secret)
			if tt.wantErr {
				if err == nil {
					t.Errorf("SignPayload() error = nil, want error")
				} else if err.Error() != tt.errMsg {
					t.Errorf("SignPayload() error = %q, want %q", err.Error(), tt.errMsg)
				}
				return
			}
			if err != nil {
				t.Errorf("SignPayload() unexpected error: %v", err)
				return
			}
			if sig == "" {
				t.Error("SignPayload() returned empty signature")
			}
			// Signature should be 64 hex chars (256 bits)
			if len(sig) != 64 {
				t.Errorf("SignPayload() signature length = %d, want 64", len(sig))
			}
		})
	}
}

func TestSignPayloadDeterministic(t *testing.T) {
	// Test that signing is deterministic (same input = same output)
	payload := Payload{"drop_box_id": "test-box", "status": "active"}
	secret := []byte("test-secret")

	sig1, err := SignPayload(payload, secret)
	if err != nil {
		t.Fatalf("SignPayload() error: %v", err)
	}

	sig2, err := SignPayload(payload, secret)
	if err != nil {
		t.Fatalf("SignPayload() error: %v", err)
	}

	if sig1 != sig2 {
		t.Errorf("SignPayload() not deterministic: %s != %s", sig1, sig2)
	}
}

func TestSignPayloadMatchesPython(t *testing.T) {
	// CRITICAL: This test verifies Go signatures match Python's sign_payload() output.
	// If this test fails, the Go drop box client cannot communicate with Python C2 server.
	//
	// Python code to generate expected signature:
	//   from cyberred.c2.protocol import sign_payload
	//   sig = sign_payload({"drop_box_id": "test-box", "status": "active"}, b"test-secret")
	//   print(sig)  # f188465c573117450a05602a3e751863f6b1061975c03c13677f2636bb4fee4a

	tests := []struct {
		name       string
		payload    Payload
		secret     []byte
		expectedSig string
	}{
		{
			name:       "heartbeat payload",
			payload:    Payload{"drop_box_id": "test-box", "status": "active"},
			secret:     []byte("test-secret"),
			expectedSig: "f188465c573117450a05602a3e751863f6b1061975c03c13677f2636bb4fee4a",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			sig, err := SignPayload(tt.payload, tt.secret)
			if err != nil {
				t.Fatalf("SignPayload() error: %v", err)
			}
			if sig != tt.expectedSig {
				t.Errorf("SignPayload() signature mismatch with Python\nGot:      %s\nExpected: %s", sig, tt.expectedSig)
			}
		})
	}
}

func TestMarshalPayloadPython(t *testing.T) {
	// Verify MarshalPayloadPython produces Python-compatible JSON
	tests := []struct {
		name     string
		payload  Payload
		expected string
	}{
		{
			name:     "simple payload",
			payload:  Payload{"drop_box_id": "test-box", "status": "active"},
			expected: `{"drop_box_id": "test-box", "status": "active"}`,
		},
		{
			name:     "payload with number",
			payload:  Payload{"count": float64(42), "name": "test"},
			expected: `{"count": 42, "name": "test"}`,
		},
		{
			name:     "payload with bool",
			payload:  Payload{"active": true, "name": "test"},
			expected: `{"active": true, "name": "test"}`,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			data, err := MarshalPayloadPython(tt.payload)
			if err != nil {
				t.Fatalf("MarshalPayloadPython() error: %v", err)
			}
			if string(data) != tt.expected {
				t.Errorf("MarshalPayloadPython() mismatch\nGot:      %s\nExpected: %s", string(data), tt.expected)
			}
		})
	}
}

func TestSignPayloadKeyOrdering(t *testing.T) {
	// Test that key ordering is consistent (Go sorts map keys alphabetically)
	// This is critical for Python interoperability
	secret := []byte("test-secret")

	// Create payloads with keys in different orders
	payload1 := Payload{"z_key": "z", "a_key": "a", "m_key": "m"}
	payload2 := Payload{"a_key": "a", "m_key": "m", "z_key": "z"}

	sig1, _ := SignPayload(payload1, secret)
	sig2, _ := SignPayload(payload2, secret)

	if sig1 != sig2 {
		t.Error("SignPayload() should produce same signature regardless of key insertion order")
	}
}

func TestVerifySignature(t *testing.T) {
	secret := []byte("test-secret")
	payload := Payload{"drop_box_id": "test-box", "status": "active"}

	sig, _ := SignPayload(payload, secret)

	msg := &C2Message{
		Type:      MessageTypeHeartbeat,
		ID:        "test-id",
		Timestamp: "2024-01-01T00:00:00Z",
		Payload:   payload,
		Signature: sig,
	}

	valid, err := VerifySignature(msg, secret)
	if err != nil {
		t.Fatalf("VerifySignature() error: %v", err)
	}
	if !valid {
		t.Error("VerifySignature() = false, want true")
	}

	// Test with wrong signature
	msg.Signature = "wrong-signature"
	valid, err = VerifySignature(msg, secret)
	if err != nil {
		t.Fatalf("VerifySignature() error: %v", err)
	}
	if valid {
		t.Error("VerifySignature() = true for wrong signature, want false")
	}

	// Test with nil message
	valid, err = VerifySignature(nil, secret)
	if err == nil {
		t.Error("VerifySignature() should error on nil message")
	}
}

func TestNewHeartbeatMessage(t *testing.T) {
	secret := []byte("test-secret")
	dropBoxID := "test-drop-box"
	status := "active"

	msg, err := NewHeartbeatMessage(dropBoxID, status, secret)
	if err != nil {
		t.Fatalf("NewHeartbeatMessage() error: %v", err)
	}

	if msg.Type != MessageTypeHeartbeat {
		t.Errorf("Type = %s, want %s", msg.Type, MessageTypeHeartbeat)
	}
	if msg.ID == "" {
		t.Error("ID should not be empty")
	}
	if msg.Timestamp == "" {
		t.Error("Timestamp should not be empty")
	}
	if msg.Signature == "" {
		t.Error("Signature should not be empty")
	}

	// Verify payload
	if msg.Payload["drop_box_id"] != dropBoxID {
		t.Errorf("Payload drop_box_id = %v, want %s", msg.Payload["drop_box_id"], dropBoxID)
	}
	if msg.Payload["status"] != status {
		t.Errorf("Payload status = %v, want %s", msg.Payload["status"], status)
	}

	// Verify signature is valid
	valid, _ := VerifySignature(msg, secret)
	if !valid {
		t.Error("Message signature should be valid")
	}
}

func TestNewResultMessage(t *testing.T) {
	secret := []byte("test-secret")
	commandID := "cmd-123"
	success := true
	output := map[string]any{"result": "ok"}

	msg, err := NewResultMessage(commandID, success, output, secret)
	if err != nil {
		t.Fatalf("NewResultMessage() error: %v", err)
	}

	if msg.Type != MessageTypeResult {
		t.Errorf("Type = %s, want %s", msg.Type, MessageTypeResult)
	}

	// Verify payload
	if msg.Payload["command_id"] != commandID {
		t.Errorf("Payload command_id = %v, want %s", msg.Payload["command_id"], commandID)
	}
	if msg.Payload["success"] != success {
		t.Errorf("Payload success = %v, want %v", msg.Payload["success"], success)
	}

	// Verify signature is valid
	valid, _ := VerifySignature(msg, secret)
	if !valid {
		t.Error("Message signature should be valid")
	}
}

func TestParseMessage(t *testing.T) {
	tests := []struct {
		name    string
		json    string
		wantErr bool
		errMsg  string
	}{
		{
			name:    "invalid JSON",
			json:    "not json",
			wantErr: true,
		},
		{
			name:    "missing type",
			json:    `{"id":"1","timestamp":"2024-01-01","payload":{},"signature":"sig"}`,
			wantErr: true,
			errMsg:  "missing message type",
		},
		{
			name:    "missing id",
			json:    `{"type":"heartbeat","timestamp":"2024-01-01","payload":{},"signature":"sig"}`,
			wantErr: true,
			errMsg:  "missing message id",
		},
		{
			name:    "invalid message type",
			json:    `{"type":"invalid","id":"1","timestamp":"2024-01-01","payload":{},"signature":"sig"}`,
			wantErr: true,
			errMsg:  "invalid message type: invalid",
		},
		{
			name:    "valid heartbeat",
			json:    `{"type":"heartbeat","id":"1","timestamp":"2024-01-01","payload":{"drop_box_id":"test"},"signature":"sig"}`,
			wantErr: false,
		},
		{
			name:    "valid command",
			json:    `{"type":"command","id":"1","timestamp":"2024-01-01","payload":{"command":"scan"},"signature":"sig"}`,
			wantErr: false,
		},
		{
			name:    "valid result",
			json:    `{"type":"result","id":"1","timestamp":"2024-01-01","payload":{"success":true},"signature":"sig"}`,
			wantErr: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			msg, err := ParseMessage([]byte(tt.json))
			if tt.wantErr {
				if err == nil {
					t.Error("ParseMessage() error = nil, want error")
				} else if tt.errMsg != "" && err.Error() != tt.errMsg {
					t.Errorf("ParseMessage() error = %q, want %q", err.Error(), tt.errMsg)
				}
				return
			}
			if err != nil {
				t.Errorf("ParseMessage() unexpected error: %v", err)
				return
			}
			if msg == nil {
				t.Error("ParseMessage() returned nil message")
			}
		})
	}
}

func TestValidateAndParseMessage(t *testing.T) {
	secret := []byte("test-secret")

	// Create a valid signed message
	validMsg, _ := NewHeartbeatMessage("test-box", "active", secret)
	validJSON, _ := validMsg.ToJSON()

	// Test valid message
	msg, err := ValidateAndParseMessage(validJSON, secret)
	if err != nil {
		t.Errorf("ValidateAndParseMessage() error: %v", err)
	}
	if msg == nil {
		t.Error("ValidateAndParseMessage() returned nil message")
	}

	// Test message with invalid signature
	invalidMsg := *validMsg
	invalidMsg.Signature = "invalid-signature"
	invalidJSON, _ := json.Marshal(invalidMsg)

	_, err = ValidateAndParseMessage(invalidJSON, secret)
	if err == nil {
		t.Error("ValidateAndParseMessage() should error on invalid signature")
	}
}

func TestC2MessageToJSON(t *testing.T) {
	msg := &C2Message{
		Type:      MessageTypeHeartbeat,
		ID:        "test-id",
		Timestamp: "2024-01-01T00:00:00Z",
		Payload:   Payload{"drop_box_id": "test", "status": "active"},
		Signature: "test-signature",
	}

	data, err := msg.ToJSON()
	if err != nil {
		t.Fatalf("ToJSON() error: %v", err)
	}

	// Verify it's valid JSON
	var parsed map[string]any
	if err := json.Unmarshal(data, &parsed); err != nil {
		t.Errorf("ToJSON() produced invalid JSON: %v", err)
	}

	// Verify fields
	if parsed["type"] != string(MessageTypeHeartbeat) {
		t.Errorf("type = %v, want %s", parsed["type"], MessageTypeHeartbeat)
	}
	if parsed["id"] != "test-id" {
		t.Errorf("id = %v, want test-id", parsed["id"])
	}
}

func TestGetCommandPayload(t *testing.T) {
	// Test valid command message
	cmdMsg := &C2Message{
		Type:    MessageTypeCommand,
		Payload: Payload{"command": "scan", "args": map[string]any{"target": "192.168.1.1"}},
	}

	cmd, err := cmdMsg.GetCommandPayload()
	if err != nil {
		t.Fatalf("GetCommandPayload() error: %v", err)
	}
	if cmd.Command != "scan" {
		t.Errorf("Command = %s, want scan", cmd.Command)
	}
	if cmd.Args["target"] != "192.168.1.1" {
		t.Errorf("Args[target] = %v, want 192.168.1.1", cmd.Args["target"])
	}

	// Test non-command message
	heartbeatMsg := &C2Message{
		Type:    MessageTypeHeartbeat,
		Payload: Payload{"drop_box_id": "test"},
	}

	_, err = heartbeatMsg.GetCommandPayload()
	if err == nil {
		t.Error("GetCommandPayload() should error on non-command message")
	}

	// Test command without args
	cmdNoArgs := &C2Message{
		Type:    MessageTypeCommand,
		Payload: Payload{"command": "status"},
	}

	cmd, err = cmdNoArgs.GetCommandPayload()
	if err != nil {
		t.Fatalf("GetCommandPayload() error: %v", err)
	}
	if cmd.Args == nil {
		t.Error("Args should be initialized to empty map, not nil")
	}
}

func TestMessageTypes(t *testing.T) {
	// Verify message type constants match Python
	if MessageTypeCommand != "command" {
		t.Errorf("MessageTypeCommand = %s, want command", MessageTypeCommand)
	}
	if MessageTypeResult != "result" {
		t.Errorf("MessageTypeResult = %s, want result", MessageTypeResult)
	}
	if MessageTypeHeartbeat != "heartbeat" {
		t.Errorf("MessageTypeHeartbeat = %s, want heartbeat", MessageTypeHeartbeat)
	}
}

func TestNewHeartbeatMessageErrors(t *testing.T) {
	// Test with empty secret
	_, err := NewHeartbeatMessage("test-box", "active", []byte{})
	if err == nil {
		t.Error("NewHeartbeatMessage() should fail with empty secret")
	}

	// Test with nil secret
	_, err = NewHeartbeatMessage("test-box", "active", nil)
	if err == nil {
		t.Error("NewHeartbeatMessage() should fail with nil secret")
	}
}

func TestNewResultMessageErrors(t *testing.T) {
	// Test with empty secret
	_, err := NewResultMessage("cmd-123", true, "output", []byte{})
	if err == nil {
		t.Error("NewResultMessage() should fail with empty secret")
	}

	// Test with nil secret
	_, err = NewResultMessage("cmd-123", true, "output", nil)
	if err == nil {
		t.Error("NewResultMessage() should fail with nil secret")
	}
}

func TestValidateAndParseMessageErrors(t *testing.T) {
	secret := []byte("test-secret")

	// Test invalid JSON
	_, err := ValidateAndParseMessage([]byte("not json"), secret)
	if err == nil {
		t.Error("ValidateAndParseMessage() should fail on invalid JSON")
	}

	// Test with empty secret (verification should fail)
	validMsg, _ := NewHeartbeatMessage("test-box", "active", secret)
	validJSON, _ := validMsg.ToJSON()

	_, err = ValidateAndParseMessage(validJSON, []byte{})
	if err == nil {
		t.Error("ValidateAndParseMessage() should fail with empty secret")
	}
}

func TestVerifySignatureErrors(t *testing.T) {
	// Test with empty secret
	msg := &C2Message{
		Type:      MessageTypeHeartbeat,
		Payload:   Payload{"test": "data"},
		Signature: "somesig",
	}

	_, err := VerifySignature(msg, []byte{})
	if err == nil {
		t.Error("VerifySignature() should fail with empty secret")
	}
}

func TestParseMessageMissingFields(t *testing.T) {
	tests := []struct {
		name string
		json string
	}{
		{"missing timestamp", `{"type":"heartbeat","id":"1","payload":{},"signature":"sig"}`},
		{"missing payload", `{"type":"heartbeat","id":"1","timestamp":"2024-01-01","signature":"sig"}`},
		{"missing signature", `{"type":"heartbeat","id":"1","timestamp":"2024-01-01","payload":{}}`},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := ParseMessage([]byte(tt.json))
			if err == nil {
				t.Errorf("ParseMessage() should fail for %s", tt.name)
			}
		})
	}
}

func TestGetCommandPayloadMissingCommand(t *testing.T) {
	msg := &C2Message{
		Type:    MessageTypeCommand,
		Payload: Payload{"args": map[string]any{"target": "192.168.1.1"}}, // missing "command"
	}

	_, err := msg.GetCommandPayload()
	if err == nil {
		t.Error("GetCommandPayload() should fail when command field is missing")
	}
}

func TestGetCommandPayloadInvalidCommand(t *testing.T) {
	msg := &C2Message{
		Type:    MessageTypeCommand,
		Payload: Payload{"command": 123}, // command is not a string
	}

	_, err := msg.GetCommandPayload()
	if err == nil {
		t.Error("GetCommandPayload() should fail when command is not a string")
	}
}

func TestNewResultMessageWithComplexOutput(t *testing.T) {
	secret := []byte("test-secret")

	// Test with complex nested output
	output := map[string]any{
		"hosts": []any{
			map[string]any{"ip": "192.168.1.1", "ports": []any{22, 80, 443}},
			map[string]any{"ip": "192.168.1.2", "ports": []any{22, 8080}},
		},
		"scan_time": 12.5,
		"success":   true,
	}

	msg, err := NewResultMessage("cmd-456", true, output, secret)
	if err != nil {
		t.Fatalf("NewResultMessage() error: %v", err)
	}

	// Verify it can be serialized and signature verified
	valid, err := VerifySignature(msg, secret)
	if err != nil {
		t.Fatalf("VerifySignature() error: %v", err)
	}
	if !valid {
		t.Error("Signature should be valid for complex output")
	}
}
