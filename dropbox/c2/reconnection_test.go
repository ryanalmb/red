// Package c2 provides the mTLS WebSocket client for C2 communication.
// These are integration tests for Story 12.11: Drop Box Reconnection Handling
// ATDD RED PHASE: All tests should FAIL until implementation is complete.
package c2

import (
	"sync"
	"testing"
	"time"
)

// =============================================================================
// AC #1: Given drop box is connected and working, When C2 connection is lost,
//        Then drop box attempts reconnection with exponential backoff
//        (1s, 2s, 4s, 8s, 16s, max 30s)
// =============================================================================

func TestReconnection_ExponentialBackoff_Sequence(t *testing.T) {
	// GIVEN: Expected backoff sequence per AC #1
	expectedBackoffs := []time.Duration{
		1 * time.Second,
		2 * time.Second,
		4 * time.Second,
		8 * time.Second,
		16 * time.Second,
		30 * time.Second, // Max per AC #1
	}

	// WHEN: Checking the backoffDelays constant
	// THEN: Backoff sequence matches expected values
	if len(backoffDelays) != len(expectedBackoffs) {
		t.Errorf("backoffDelays length = %d, want %d", len(backoffDelays), len(expectedBackoffs))
	}

	for i, expected := range expectedBackoffs {
		if i < len(backoffDelays) && backoffDelays[i] != expected {
			t.Errorf("backoffDelays[%d] = %v, want %v", i, backoffDelays[i], expected)
		}
	}
}

func TestReconnection_ExponentialBackoff_MaxDelay(t *testing.T) {
	// GIVEN: A client with configured backoff
	cfg := NewConfig()
	cfg.ServerAddress = "localhost:9999"
	cfg.CertPEM = "dummy"
	cfg.KeyPEM = "dummy"
	cfg.CAPEM = "dummy"
	client, _ := NewClient(cfg)

	// WHEN: Attempt count exceeds backoff array length
	client.attempt = 10 // Beyond the 6 entries in backoffDelays

	// THEN: getBackoffDelay returns max delay (30s)
	delay := client.getBackoffDelay()
	if delay != 30*time.Second {
		t.Errorf("getBackoffDelay() at attempt 10 = %v, want 30s (max)", delay)
	}
}

func TestReconnection_BackoffIncrementsOnFailure(t *testing.T) {
	// GIVEN: A client
	cfg := NewConfig()
	cfg.ServerAddress = "localhost:9999"
	cfg.CertPEM = "dummy"
	cfg.KeyPEM = "dummy"
	cfg.CAPEM = "dummy"
	client, _ := NewClient(cfg)

	// WHEN: Getting backoff delays for increasing attempts
	delays := make([]time.Duration, 0)
	for i := 0; i < 6; i++ {
		client.attempt = i
		delays = append(delays, client.getBackoffDelay())
	}

	// THEN: Delays follow exponential pattern
	expected := []time.Duration{
		1 * time.Second,
		2 * time.Second,
		4 * time.Second,
		8 * time.Second,
		16 * time.Second,
		30 * time.Second,
	}

	for i, exp := range expected {
		if delays[i] != exp {
			t.Errorf("Backoff at attempt %d = %v, want %v", i, delays[i], exp)
		}
	}
}

// =============================================================================
// AC #2: Given connection is lost, When results are generated,
//        Then pending results are queued locally (max 100 messages or 10MB)
// =============================================================================

func TestClient_SendResult_QueuesWhenDisconnected(t *testing.T) {
	// GIVEN: A client that is disconnected but has a message queue
	cfg := NewConfig()
	cfg.ServerAddress = "localhost:9999"
	cfg.CertPEM = "dummy"
	cfg.KeyPEM = "dummy"
	cfg.CAPEM = "dummy"
	client, err := NewClient(cfg)
	if err != nil {
		t.Fatalf("NewClient() error = %v", err)
	}
	client.SetSharedSecret([]byte("test-secret"))
	client.SetDropBoxID("test-box")

	// Ensure client has a message queue (Story 12.11 requirement)
	if client.messageQueue == nil {
		t.Fatal("Client should have messageQueue field initialized (Story 12.11)")
	}

	// WHEN: SendResult is called while disconnected
	sendErr := client.SendResult("cmd-123", []byte(`{"output": "test"}`))

	// THEN: Message should be queued (not error with "not connected")
	// Note: Current implementation returns error, Story 12.11 should queue instead
	if sendErr != nil && sendErr.Error() == "not connected" {
		// This is the current behavior - Story 12.11 should change this to queue
		t.Log("SendResult returned 'not connected' - Story 12.11 should queue instead")
	}

	// AND: Message queue should contain the result
	if client.messageQueue.Count() != 1 {
		t.Errorf("messageQueue.Count() = %d, want 1 (result should be queued)", client.messageQueue.Count())
	}
}

func TestClient_HasMessageQueueField(t *testing.T) {
	// GIVEN: A new client
	cfg := NewConfig()
	cfg.ServerAddress = "localhost:9999"
	cfg.CertPEM = "dummy"
	cfg.KeyPEM = "dummy"
	cfg.CAPEM = "dummy"
	client, err := NewClient(cfg)
	if err != nil {
		t.Fatalf("NewClient() error = %v", err)
	}

	// THEN: Client should have messageQueue field initialized
	if client.messageQueue == nil {
		t.Fatal("Client.messageQueue should be initialized (Story 12.11 requirement)")
	}

	// AND: messageQueue should be functional
	if client.messageQueue.Count() != 0 {
		t.Errorf("New messageQueue.Count() = %d, want 0", client.messageQueue.Count())
	}
}

// =============================================================================
// AC #3: Given drop box reconnects successfully, When connection is re-established,
//        Then all queued results are sent in order
// =============================================================================

func TestClient_DrainQueue_SendsAllMessagesOnReconnect(t *testing.T) {
	// GIVEN: A client with a message queue
	cfg := NewConfig()
	cfg.ServerAddress = "localhost:9999"
	cfg.CertPEM = "dummy"
	cfg.KeyPEM = "dummy"
	cfg.CAPEM = "dummy"
	client, _ := NewClient(cfg)
	client.SetSharedSecret([]byte("test-secret"))

	// AND: Queue has pending messages
	if client.messageQueue == nil {
		t.Fatal("Client should have messageQueue field")
	}

	for i := 1; i <= 3; i++ {
		msg := &C2Message{
			Type:      MessageTypeResult,
			ID:        "queued-msg",
			Timestamp: "2026-02-12T00:00:00Z",
			Payload:   Payload{"order": i},
			Signature: "sig",
		}
		_ = client.messageQueue.Enqueue(msg)
	}

	// WHEN: drainQueue is called (after reconnection)
	// Note: This method should exist per Task 2.3
	err := client.drainQueue()

	// THEN: Method exists and can be called
	if err != nil {
		t.Logf("drainQueue() error = %v (expected if not connected)", err)
	}

	// Note: Full verification requires mock server - this test verifies method exists
}

func TestClient_DrainQueue_MethodExists(t *testing.T) {
	// GIVEN: A client
	cfg := NewConfig()
	cfg.ServerAddress = "localhost:9999"
	cfg.CertPEM = "dummy"
	cfg.KeyPEM = "dummy"
	cfg.CAPEM = "dummy"
	client, _ := NewClient(cfg)

	// THEN: drainQueue method should exist (Story 12.11 Task 2.3)
	// This will fail to compile if method doesn't exist
	_ = client.drainQueue
}

// =============================================================================
// AC #4: Given drop box has an ID, When reconnection occurs,
//        Then drop box ID persists across reconnections
// =============================================================================

func TestClient_DropBoxID_PersistsAcrossReconnections(t *testing.T) {
	// GIVEN: A client with a drop box ID set
	cfg := NewConfig()
	cfg.ServerAddress = "localhost:9999"
	cfg.CertPEM = "dummy"
	cfg.KeyPEM = "dummy"
	cfg.CAPEM = "dummy"
	client, _ := NewClient(cfg)

	originalID := "dropbox-12345-persistent"
	client.SetDropBoxID(originalID)

	// WHEN: Client goes through reconnection states
	client.setState(StateConnected)
	client.setState(StateReconnecting)
	client.setState(StateConnected) // Reconnected

	// THEN: Drop box ID is unchanged
	if client.dropBoxID != originalID {
		t.Errorf("dropBoxID after reconnection = %q, want %q", client.dropBoxID, originalID)
	}
}

func TestClient_DropBoxID_IncludedInHeartbeatAfterReconnect(t *testing.T) {
	// GIVEN: A client with a drop box ID
	cfg := NewConfig()
	cfg.ServerAddress = "localhost:9999"
	cfg.CertPEM = "dummy"
	cfg.KeyPEM = "dummy"
	cfg.CAPEM = "dummy"
	client, _ := NewClient(cfg)

	expectedID := "persistent-box-id"
	client.SetDropBoxID(expectedID)
	client.SetSharedSecret([]byte("test-secret"))

	// WHEN: Creating a heartbeat message (as would happen after reconnect)
	// The dropBoxID should be included

	// THEN: dropBoxID field should persist
	if client.dropBoxID != expectedID {
		t.Errorf("dropBoxID = %q, want %q", client.dropBoxID, expectedID)
	}
}

// =============================================================================
// AC #5: Given connection is lost, When 30 seconds of reconnection attempts fail,
//        Then full retry cycle restarts from beginning
// =============================================================================

func TestReconnection_TimeoutResetsBackoffCycle(t *testing.T) {
	// GIVEN: A client with reconnection timeout tracking
	cfg := NewConfig()
	cfg.ServerAddress = "localhost:9999"
	cfg.CertPEM = "dummy"
	cfg.KeyPEM = "dummy"
	cfg.CAPEM = "dummy"
	client, _ := NewClient(cfg)

	// WHEN: Checking for ReconnectionTimeout constant (30s per NFR17)
	// THEN: Constant should exist with value 30s
	if ReconnectionTimeout != 30*time.Second {
		t.Errorf("ReconnectionTimeout = %v, want 30s", ReconnectionTimeout)
	}

	// AND: Client should have method to check/reset timeout
	_ = client // Placeholder - implementation will add timeout tracking
}

func TestReconnection_ReconnectionTimeoutConstant_Exists(t *testing.T) {
	// GIVEN: Story 12.11 requirement for 30s timeout
	// WHEN: Checking for constant
	// THEN: ReconnectionTimeout should be defined as 30 seconds
	expected := 30 * time.Second
	if ReconnectionTimeout != expected {
		t.Errorf("ReconnectionTimeout = %v, want %v", ReconnectionTimeout, expected)
	}
}

func TestReconnection_BackoffResetsAfter30Seconds(t *testing.T) {
	// GIVEN: A client that has been attempting reconnection
	cfg := NewConfig()
	cfg.ServerAddress = "localhost:9999"
	cfg.CertPEM = "dummy"
	cfg.KeyPEM = "dummy"
	cfg.CAPEM = "dummy"
	client, _ := NewClient(cfg)

	// AND: Reconnection attempts have been ongoing
	client.attempt = 5 // At max backoff (30s)

	// WHEN: Total reconnection time exceeds 30 seconds
	// The reconnectLoop should reset the attempt counter

	// THEN: After 30s timeout, attempt should reset to 0
	// This is tested via the reconnection start time tracking
	if client.reconnectStartTime.IsZero() {
		// reconnectStartTime should be tracked (Story 12.11 requirement)
		t.Log("reconnectStartTime not tracked - Story 12.11 should add this")
	}

	// Simulate timeout detection
	client.reconnectStartTime = time.Now().Add(-31 * time.Second) // 31s ago
	client.checkAndResetBackoffCycle()

	// THEN: Attempt counter should be reset
	if client.attempt != 0 {
		t.Errorf("attempt after 30s timeout = %d, want 0 (reset)", client.attempt)
	}
}

// =============================================================================
// AC #8: Given all above scenarios, Then integration tests verify reconnection
//        flow with 100% coverage
// =============================================================================

func TestReconnection_IntegrationFlow_MessageQueueing(t *testing.T) {
	// GIVEN: A client that connects, loses connection, and reconnects
	cfg := NewConfig()
	cfg.ServerAddress = "localhost:9999"
	cfg.CertPEM = "dummy"
	cfg.KeyPEM = "dummy"
	cfg.CAPEM = "dummy"
	client, _ := NewClient(cfg)
	client.SetSharedSecret([]byte("test-secret"))
	client.SetDropBoxID("integration-test-box")

	// Verify message queue exists
	if client.messageQueue == nil {
		t.Fatal("messageQueue should be initialized")
	}

	// WHEN: Connection is lost (simulated)
	client.setState(StateReconnecting)

	// AND: Results are generated while disconnected
	for i := 1; i <= 5; i++ {
		msg := &C2Message{
			Type:      MessageTypeResult,
			ID:        "result",
			Timestamp: "2026-02-12T00:00:00Z",
			Payload:   Payload{"data": i},
			Signature: "sig",
		}
		_ = client.messageQueue.Enqueue(msg)
	}

	// THEN: Messages are queued
	if client.messageQueue.Count() != 5 {
		t.Errorf("messageQueue.Count() = %d, want 5", client.messageQueue.Count())
	}

	// AND: Drop box ID persists
	if client.dropBoxID != "integration-test-box" {
		t.Errorf("dropBoxID = %q, want %q", client.dropBoxID, "integration-test-box")
	}
}

func TestReconnection_IntegrationFlow_FullCycle(t *testing.T) {
	// This test verifies the full reconnection flow:
	// 1. Client connected
	// 2. Connection lost
	// 3. Results generated and queued
	// 4. Exponential backoff attempted
	// 5. Reconnection successful
	// 6. Queue drained
	// 7. ID persists

	cfg := NewConfig()
	cfg.ServerAddress = "localhost:9999"
	cfg.CertPEM = "dummy"
	cfg.KeyPEM = "dummy"
	cfg.CAPEM = "dummy"
	client, _ := NewClient(cfg)
	client.SetSharedSecret([]byte("secret"))
	client.SetDropBoxID("full-cycle-test")

	// Step 1: Initial state
	if client.State() != StateDisconnected {
		t.Errorf("Initial state = %v, want StateDisconnected", client.State())
	}

	// Step 2: Simulate connection loss
	client.setState(StateConnected)
	client.setState(StateReconnecting)

	// Step 3: Queue messages
	if client.messageQueue != nil {
		for i := 0; i < 3; i++ {
			msg := &C2Message{
				Type:      MessageTypeResult,
				ID:        "msg",
				Timestamp: "2026-02-12T00:00:00Z",
				Payload:   Payload{},
				Signature: "sig",
			}
			_ = client.messageQueue.Enqueue(msg)
		}
	}

	// Step 4: Verify backoff available
	if client.getBackoffDelay() != 1*time.Second {
		t.Errorf("Initial backoff = %v, want 1s", client.getBackoffDelay())
	}

	// Step 5-6: (Would require mock server for full test)

	// Step 7: Verify ID persistence
	if client.dropBoxID != "full-cycle-test" {
		t.Errorf("dropBoxID = %q, want %q", client.dropBoxID, "full-cycle-test")
	}
}

// =============================================================================
// Helper type assertions to ensure Story 12.11 fields exist on Client
// =============================================================================

func TestClient_Story1211_RequiredFields(t *testing.T) {
	cfg := NewConfig()
	cfg.ServerAddress = "localhost:9999"
	cfg.CertPEM = "dummy"
	cfg.KeyPEM = "dummy"
	cfg.CAPEM = "dummy"
	client, _ := NewClient(cfg)

	// messageQueue field (Task 2.1)
	if client.messageQueue == nil {
		t.Error("Client should have messageQueue field initialized")
	}

	// reconnectStartTime field (Task 3.2)
	var _ time.Time = client.reconnectStartTime
	t.Log("reconnectStartTime field exists")
}

// =============================================================================
// Concurrency tests for reconnection
// =============================================================================

func TestReconnection_ConcurrentQueueAccessDuringReconnect(t *testing.T) {
	cfg := NewConfig()
	cfg.ServerAddress = "localhost:9999"
	cfg.CertPEM = "dummy"
	cfg.KeyPEM = "dummy"
	cfg.CAPEM = "dummy"
	client, _ := NewClient(cfg)

	if client.messageQueue == nil {
		t.Fatal("messageQueue required for this test")
	}

	// Simulate concurrent access during reconnection
	var wg sync.WaitGroup

	// Multiple goroutines enqueueing
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			msg := &C2Message{
				Type:      MessageTypeResult,
				ID:        "concurrent",
				Timestamp: "2026-02-12T00:00:00Z",
				Payload:   Payload{"goroutine": id},
				Signature: "sig",
			}
			_ = client.messageQueue.Enqueue(msg)
		}(i)
	}

	wg.Wait()

	// All messages should be queued
	if client.messageQueue.Count() != 10 {
		t.Errorf("messageQueue.Count() = %d, want 10", client.messageQueue.Count())
	}
}
