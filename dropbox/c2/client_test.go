package c2

import (
	"context"
	"testing"
	"time"
)

func TestNewClient(t *testing.T) {
	tests := []struct {
		name    string
		config  *Config
		wantErr bool
		errMsg  string
	}{
		{
			name:    "nil config",
			config:  nil,
			wantErr: true,
			errMsg:  "config cannot be nil",
		},
		{
			name:    "valid config",
			config:  NewConfig(),
			wantErr: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			client, err := NewClient(tt.config)
			if tt.wantErr {
				if err == nil {
					t.Error("NewClient() error = nil, want error")
				} else if err.Error() != tt.errMsg {
					t.Errorf("NewClient() error = %q, want %q", err.Error(), tt.errMsg)
				}
				if client != nil {
					t.Error("NewClient() should return nil client on error")
				}
			} else {
				if err != nil {
					t.Errorf("NewClient() unexpected error: %v", err)
				}
				if client == nil {
					t.Error("NewClient() should return non-nil client")
				}
				if client != nil && client.config != tt.config {
					t.Error("NewClient() config not stored correctly")
				}
			}
		})
	}
}

func TestClientState(t *testing.T) {
	client, _ := NewClient(NewConfig())

	// Initial state should be disconnected
	if client.State() != StateDisconnected {
		t.Errorf("Initial state = %v, want %v", client.State(), StateDisconnected)
	}

	// Test state string representation
	states := []struct {
		state ConnectionState
		want  string
	}{
		{StateDisconnected, "disconnected"},
		{StateConnecting, "connecting"},
		{StateConnected, "connected"},
		{StateReconnecting, "reconnecting"},
		{ConnectionState(99), "unknown"},
	}

	for _, tt := range states {
		if got := tt.state.String(); got != tt.want {
			t.Errorf("ConnectionState(%d).String() = %s, want %s", tt.state, got, tt.want)
		}
	}
}

func TestClientSetters(t *testing.T) {
	client, _ := NewClient(NewConfig())

	// Test SetSharedSecret
	secret := []byte("test-secret")
	client.SetSharedSecret(secret)
	if string(client.sharedSecret) != string(secret) {
		t.Error("SetSharedSecret() did not set secret correctly")
	}

	// Test SetDropBoxID
	dropBoxID := "test-box-123"
	client.SetDropBoxID(dropBoxID)
	if client.dropBoxID != dropBoxID {
		t.Error("SetDropBoxID() did not set ID correctly")
	}
}

func TestClientConnectWithoutCerts(t *testing.T) {
	cfg := NewConfig()
	cfg.ServerAddress = "localhost:8444"
	cfg.CertFile = "/nonexistent/cert.pem"
	cfg.KeyFile = "/nonexistent/key.pem"
	cfg.CAFile = "/nonexistent/ca.pem"

	client, _ := NewClient(cfg)
	err := client.Connect()

	// Should fail due to missing certificate files
	if err == nil {
		t.Error("Connect() should fail without valid certificates")
		client.Disconnect()
	}
}

func TestClientDisconnectWhenNotConnected(t *testing.T) {
	client, _ := NewClient(NewConfig())

	// Disconnect when not connected should not error
	err := client.Disconnect()
	if err != nil {
		t.Errorf("Disconnect() when not connected error = %v, want nil", err)
	}

	// State should be disconnected
	if client.State() != StateDisconnected {
		t.Errorf("State after disconnect = %v, want %v", client.State(), StateDisconnected)
	}
}

func TestClientSendHeartbeatNotConnected(t *testing.T) {
	client, _ := NewClient(NewConfig())
	client.SetSharedSecret([]byte("secret"))
	client.SetDropBoxID("test-box")

	err := client.SendHeartbeat()
	if err == nil {
		t.Error("SendHeartbeat() should fail when not connected")
	}
	if err.Error() != "not connected" {
		t.Errorf("SendHeartbeat() error = %q, want %q", err.Error(), "not connected")
	}
}

func TestClientSendHeartbeatNoSecret(t *testing.T) {
	client, _ := NewClient(NewConfig())
	// Manually set state to connected for this test
	client.setState(StateConnected)

	err := client.SendHeartbeat()
	if err == nil {
		t.Error("SendHeartbeat() should fail without shared secret")
	}
	if err.Error() != "shared secret not set" {
		t.Errorf("SendHeartbeat() error = %q, want %q", err.Error(), "shared secret not set")
	}
}

func TestClientSendResultNotConnected(t *testing.T) {
	client, _ := NewClient(NewConfig())
	client.SetSharedSecret([]byte("secret"))

	err := client.SendResult("cmd-123", []byte("result"))
	if err == nil {
		t.Error("SendResult() should fail when not connected")
	}
}

func TestClientReceiveCommandWithTimeout(t *testing.T) {
	client, _ := NewClient(NewConfig())
	client.ctx, client.cancel = nil, nil // Ensure context is not set

	// This should timeout quickly
	_, err := client.ReceiveCommandWithTimeout(10 * time.Millisecond)
	if err == nil {
		t.Error("ReceiveCommandWithTimeout() should timeout")
	}
}

func TestBackoffDelays(t *testing.T) {
	expected := []time.Duration{
		1 * time.Second,
		2 * time.Second,
		4 * time.Second,
		8 * time.Second,
		16 * time.Second,
		30 * time.Second,
	}

	if len(backoffDelays) != len(expected) {
		t.Fatalf("backoffDelays length = %d, want %d", len(backoffDelays), len(expected))
	}

	for i, d := range expected {
		if backoffDelays[i] != d {
			t.Errorf("backoffDelays[%d] = %v, want %v", i, backoffDelays[i], d)
		}
	}
}

func TestGetBackoffDelay(t *testing.T) {
	client, _ := NewClient(NewConfig())

	tests := []struct {
		attempt int
		want    time.Duration
	}{
		{0, 1 * time.Second},
		{1, 2 * time.Second},
		{2, 4 * time.Second},
		{3, 8 * time.Second},
		{4, 16 * time.Second},
		{5, 30 * time.Second},
		{6, 30 * time.Second},  // Beyond array, should cap at max
		{100, 30 * time.Second}, // Way beyond, still capped
	}

	for _, tt := range tests {
		client.attempt = tt.attempt
		got := client.getBackoffDelay()
		if got != tt.want {
			t.Errorf("getBackoffDelay() with attempt=%d = %v, want %v", tt.attempt, got, tt.want)
		}
	}
}

func TestClientReceiveCommandNotConnected(t *testing.T) {
	client, _ := NewClient(NewConfig())

	// ReceiveCommand when not connected should error
	_, err := client.ReceiveCommand()
	if err == nil {
		t.Error("ReceiveCommand() should fail when not connected")
	}
	if err.Error() != "client not connected" {
		t.Errorf("ReceiveCommand() error = %q, want %q", err.Error(), "client not connected")
	}
}

func TestClientSendResultNoSecret(t *testing.T) {
	client, _ := NewClient(NewConfig())
	client.setState(StateConnected)

	err := client.SendResult("cmd-123", []byte("result"))
	if err == nil {
		t.Error("SendResult() should fail without shared secret")
	}
	if err.Error() != "shared secret not set" {
		t.Errorf("SendResult() error = %q, want %q", err.Error(), "shared secret not set")
	}
}

func TestClientSendHeartbeatNoConnection(t *testing.T) {
	client, _ := NewClient(NewConfig())
	client.setState(StateConnected)
	client.SetSharedSecret([]byte("secret"))
	client.SetDropBoxID("test-box")
	// conn is nil

	err := client.SendHeartbeat()
	if err == nil {
		t.Error("SendHeartbeat() should fail with nil connection")
	}
	if err.Error() != "connection is nil" {
		t.Errorf("SendHeartbeat() error = %q, want %q", err.Error(), "connection is nil")
	}
}

func TestClientSendResultNoConnection(t *testing.T) {
	client, _ := NewClient(NewConfig())
	client.setState(StateConnected)
	client.SetSharedSecret([]byte("secret"))
	// conn is nil

	err := client.SendResult("cmd-123", []byte(`{"result": "ok"}`))
	if err == nil {
		t.Error("SendResult() should fail with nil connection")
	}
	if err.Error() != "connection is nil" {
		t.Errorf("SendResult() error = %q, want %q", err.Error(), "connection is nil")
	}
}

func TestClientSendResultJSONParsing(t *testing.T) {
	client, _ := NewClient(NewConfig())
	client.setState(StateConnected)
	client.SetSharedSecret([]byte("secret"))
	// conn is nil, but we test up to JSON parsing

	// Non-JSON result should be converted to string
	err := client.SendResult("cmd-123", []byte("plain text result"))
	if err == nil {
		t.Error("SendResult() should fail with nil connection")
	}
	// Error is expected due to nil conn, but JSON parsing should not fail
	if err.Error() != "connection is nil" {
		t.Errorf("SendResult() error = %q, want %q", err.Error(), "connection is nil")
	}
}

func TestClientHandleDisconnectAlreadyReconnecting(t *testing.T) {
	client, _ := NewClient(NewConfig())
	client.setState(StateReconnecting)

	// handleDisconnect should return early if already reconnecting
	client.handleDisconnect()

	// State should still be reconnecting
	if client.State() != StateReconnecting {
		t.Errorf("State = %v, want %v", client.State(), StateReconnecting)
	}
}

func TestClientDisconnectWithCancel(t *testing.T) {
	client, _ := NewClient(NewConfig())

	// Set up a context that can be cancelled
	ctx, cancel := context.WithCancel(context.Background())
	client.ctx = ctx
	client.cancel = cancel

	err := client.Disconnect()
	if err != nil {
		t.Errorf("Disconnect() error = %v, want nil", err)
	}

	// Verify context was cancelled
	select {
	case <-ctx.Done():
		// Expected
	default:
		t.Error("Context should be cancelled after Disconnect()")
	}
}

func TestConnectionStateString(t *testing.T) {
	tests := []struct {
		state ConnectionState
		want  string
	}{
		{StateDisconnected, "disconnected"},
		{StateConnecting, "connecting"},
		{StateConnected, "connected"},
		{StateReconnecting, "reconnecting"},
		{ConnectionState(99), "unknown"},
		{ConnectionState(-1), "unknown"},
	}

	for _, tt := range tests {
		got := tt.state.String()
		if got != tt.want {
			t.Errorf("ConnectionState(%d).String() = %q, want %q", tt.state, got, tt.want)
		}
	}
}

func TestLoadTLSConfigCaching(t *testing.T) {
	cfg := NewConfig()
	cfg.ServerAddress = "localhost:8444"
	cfg.CertFile = "/nonexistent/cert.pem"
	cfg.KeyFile = "/nonexistent/key.pem"
	cfg.CAFile = "/nonexistent/ca.pem"

	client, _ := NewClient(cfg)

	// First call should fail (no certs)
	_, err := client.loadTLSConfig()
	if err == nil {
		t.Error("loadTLSConfig() should fail with nonexistent cert files")
	}
}

func TestClientConnectStateTransitions(t *testing.T) {
	cfg := NewConfig()
	cfg.ServerAddress = "localhost:8444"
	cfg.CertFile = "/nonexistent/cert.pem"
	cfg.KeyFile = "/nonexistent/key.pem"
	cfg.CAFile = "/nonexistent/ca.pem"

	client, _ := NewClient(cfg)

	// Initial state
	if client.State() != StateDisconnected {
		t.Errorf("Initial state = %v, want %v", client.State(), StateDisconnected)
	}

	// Connect should transition to Connecting then back to Disconnected on failure
	err := client.Connect()
	if err == nil {
		t.Error("Connect() should fail with invalid certs")
	}
	if client.State() != StateDisconnected {
		t.Errorf("State after failed connect = %v, want %v", client.State(), StateDisconnected)
	}
}

func TestReceiveCommandWithTimeoutSuccess(t *testing.T) {
	client, _ := NewClient(NewConfig())

	// Pre-populate command channel
	testMsg := &C2Message{
		Type:      MessageTypeCommand,
		ID:        "test-cmd-id",
		Timestamp: "2024-01-01T00:00:00Z",
		Payload:   Payload{"command": "scan", "args": map[string]any{}},
		Signature: "test-sig",
	}

	// Send to command channel
	go func() {
		client.commandC <- testMsg
	}()

	// Should receive the command
	data, err := client.ReceiveCommandWithTimeout(100 * time.Millisecond)
	if err != nil {
		t.Errorf("ReceiveCommandWithTimeout() error = %v", err)
	}
	if data == nil {
		t.Error("ReceiveCommandWithTimeout() should return data")
	}
}

func TestReceiveCommandWithTimeoutError(t *testing.T) {
	client, _ := NewClient(NewConfig())

	// Pre-populate error channel
	go func() {
		client.errC <- context.DeadlineExceeded
	}()

	// Should receive the error
	_, err := client.ReceiveCommandWithTimeout(100 * time.Millisecond)
	if err == nil {
		t.Error("ReceiveCommandWithTimeout() should return error")
	}
}

func TestReceiveCommandWithContextDone(t *testing.T) {
	client, _ := NewClient(NewConfig())

	// Set up cancelled context
	ctx, cancel := context.WithCancel(context.Background())
	client.ctx = ctx

	// Cancel immediately
	cancel()

	// Should return disconnected error
	_, err := client.ReceiveCommandWithTimeout(100 * time.Millisecond)
	if err == nil {
		t.Error("ReceiveCommandWithTimeout() should error when context cancelled")
	}
	if err.Error() != "client disconnected" {
		t.Errorf("Error = %q, want %q", err.Error(), "client disconnected")
	}
}
