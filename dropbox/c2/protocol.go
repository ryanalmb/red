// Package c2 provides the mTLS WebSocket client for C2 communication.
package c2

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
)

// C2MessageType represents the type of C2 message.
type C2MessageType string

const (
	// MessageTypeCommand is a command from the C2 server.
	MessageTypeCommand C2MessageType = "command"
	// MessageTypeResult is a result from command execution.
	MessageTypeResult C2MessageType = "result"
	// MessageTypeHeartbeat is a heartbeat message.
	MessageTypeHeartbeat C2MessageType = "heartbeat"
)

// C2Message represents a C2 protocol message with HMAC-SHA256 signature.
// Wire format matches Python implementation in src/cyberred/c2/protocol.py
type C2Message struct {
	Type      C2MessageType `json:"type"`
	ID        string        `json:"id"`
	Timestamp string        `json:"timestamp"`
	Payload   Payload       `json:"payload"`
	Signature string        `json:"signature"`
}

// Payload is a type alias for the message payload.
// Using map[string]any ensures JSON keys are sorted alphabetically by Go's encoding/json.
type Payload map[string]any

// MarshalPayloadPython marshals a payload to JSON matching Python's json.dumps(sort_keys=True).
// Python uses ", " (comma-space) between items and ": " (colon-space) between key-value pairs,
// while Go's json.Marshal uses "," and ":" without spaces.
// This function ensures wire compatibility with Python's C2 server.
func MarshalPayloadPython(payload Payload) ([]byte, error) {
	// First marshal with Go's default (to get sorted keys)
	data, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}

	// Convert to Python-style JSON by adding spaces after : and ,
	// We need to be careful to only add spaces in the right places (not inside strings)
	return convertToPythonJSON(data), nil
}

// convertToPythonJSON converts Go's compact JSON to Python's spaced format.
// Go:     {"key":"value","num":123}
// Python: {"key": "value", "num": 123}
func convertToPythonJSON(data []byte) []byte {
	result := make([]byte, 0, len(data)*2) // Preallocate with room for spaces
	inString := false
	escaped := false

	for i := 0; i < len(data); i++ {
		b := data[i]

		if escaped {
			result = append(result, b)
			escaped = false
			continue
		}

		if b == '\\' && inString {
			result = append(result, b)
			escaped = true
			continue
		}

		if b == '"' {
			inString = !inString
			result = append(result, b)
			continue
		}

		if !inString {
			if b == ':' {
				result = append(result, ':', ' ')
				continue
			}
			if b == ',' {
				result = append(result, ',', ' ')
				continue
			}
		}

		result = append(result, b)
	}

	return result
}

// HeartbeatPayload represents the payload for heartbeat messages.
type HeartbeatPayload struct {
	DropBoxID string `json:"drop_box_id"`
	Status    string `json:"status"`
}

// ResultPayload represents the payload for result messages.
type ResultPayload struct {
	CommandID string `json:"command_id"`
	Success   bool   `json:"success"`
	Output    any    `json:"output"`
}

// CommandPayload represents the payload for command messages.
type CommandPayload struct {
	Command string         `json:"command"`
	Args    map[string]any `json:"args"`
}

// SignPayload generates HMAC-SHA256 signature for a payload.
// CRITICAL: This must match Python's sign_payload() exactly:
//
//	payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
//	signature = hmac.new(secret, payload_bytes, hashlib.sha256).hexdigest()
//
// Go's json.Marshal sorts map keys alphabetically, matching Python's sort_keys=True.
// However, Python's json.dumps uses ", " and ": " separators by default, while Go uses "," and ":".
// We must use custom marshaling to match Python's output exactly.
func SignPayload(payload Payload, secret []byte) (string, error) {
	if payload == nil {
		return "", errors.New("payload cannot be nil")
	}
	if len(secret) == 0 {
		return "", errors.New("secret cannot be empty")
	}

	// Use MarshalPayloadPython to match Python's json.dumps(sort_keys=True) output
	payloadBytes, err := MarshalPayloadPython(payload)
	if err != nil {
		return "", fmt.Errorf("failed to marshal payload: %w", err)
	}

	mac := hmac.New(sha256.New, secret)
	mac.Write(payloadBytes)
	return hex.EncodeToString(mac.Sum(nil)), nil
}

// VerifySignature verifies the HMAC-SHA256 signature of a message.
// Uses constant-time comparison to prevent timing attacks.
func VerifySignature(message *C2Message, secret []byte) (bool, error) {
	if message == nil {
		return false, errors.New("message cannot be nil")
	}

	expected, err := SignPayload(message.Payload, secret)
	if err != nil {
		return false, err
	}

	// Constant-time comparison for security
	return hmac.Equal([]byte(message.Signature), []byte(expected)), nil
}

// NewHeartbeatMessage creates a new heartbeat message with signature.
// Matches Python's create_heartbeat_message() in protocol.py.
func NewHeartbeatMessage(dropBoxID, status string, secret []byte) (*C2Message, error) {
	payload := Payload{
		"drop_box_id": dropBoxID,
		"status":      status,
	}

	signature, err := SignPayload(payload, secret)
	if err != nil {
		return nil, fmt.Errorf("failed to sign heartbeat: %w", err)
	}

	return &C2Message{
		Type:      MessageTypeHeartbeat,
		ID:        uuid.New().String(),
		Timestamp: time.Now().UTC().Format(time.RFC3339),
		Payload:   payload,
		Signature: signature,
	}, nil
}

// NewResultMessage creates a new result message with signature.
// Matches Python's create_result_message() in protocol.py.
func NewResultMessage(commandID string, success bool, output any, secret []byte) (*C2Message, error) {
	payload := Payload{
		"command_id": commandID,
		"success":    success,
		"output":     output,
	}

	signature, err := SignPayload(payload, secret)
	if err != nil {
		return nil, fmt.Errorf("failed to sign result: %w", err)
	}

	return &C2Message{
		Type:      MessageTypeResult,
		ID:        uuid.New().String(),
		Timestamp: time.Now().UTC().Format(time.RFC3339),
		Payload:   payload,
		Signature: signature,
	}, nil
}

// ParseMessage parses a JSON message and returns a C2Message.
func ParseMessage(data []byte) (*C2Message, error) {
	var msg C2Message
	if err := json.Unmarshal(data, &msg); err != nil {
		return nil, fmt.Errorf("failed to parse message: %w", err)
	}

	// Validate required fields
	if msg.Type == "" {
		return nil, errors.New("missing message type")
	}
	if msg.ID == "" {
		return nil, errors.New("missing message id")
	}
	if msg.Timestamp == "" {
		return nil, errors.New("missing timestamp")
	}
	if msg.Payload == nil {
		return nil, errors.New("missing payload")
	}
	if msg.Signature == "" {
		return nil, errors.New("missing signature")
	}

	// Validate message type
	switch msg.Type {
	case MessageTypeCommand, MessageTypeResult, MessageTypeHeartbeat:
		// Valid
	default:
		return nil, fmt.Errorf("invalid message type: %s", msg.Type)
	}

	return &msg, nil
}

// ValidateAndParseMessage parses and validates a C2 message including signature.
func ValidateAndParseMessage(data []byte, secret []byte) (*C2Message, error) {
	msg, err := ParseMessage(data)
	if err != nil {
		return nil, err
	}

	valid, err := VerifySignature(msg, secret)
	if err != nil {
		return nil, fmt.Errorf("signature verification failed: %w", err)
	}
	if !valid {
		return nil, errors.New("invalid signature")
	}

	return msg, nil
}

// ToJSON serializes the message to JSON bytes.
func (m *C2Message) ToJSON() ([]byte, error) {
	return json.Marshal(m)
}

// GetCommandPayload extracts command payload from a command message.
func (m *C2Message) GetCommandPayload() (*CommandPayload, error) {
	if m.Type != MessageTypeCommand {
		return nil, fmt.Errorf("not a command message: %s", m.Type)
	}

	cmd, ok := m.Payload["command"].(string)
	if !ok {
		return nil, errors.New("missing or invalid command field")
	}

	args, _ := m.Payload["args"].(map[string]any)
	if args == nil {
		args = make(map[string]any)
	}

	return &CommandPayload{
		Command: cmd,
		Args:    args,
	}, nil
}
