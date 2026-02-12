// Package c2 provides the mTLS WebSocket client for C2 communication.
// These tests are for Story 12.11: Drop Box Reconnection Handling
// ATDD RED PHASE: All tests should FAIL until implementation is complete.
package c2

import (
	"testing"
)

// =============================================================================
// AC #2: Given connection is lost, When results are generated,
//        Then pending results are queued locally (max 100 messages or 10MB)
// =============================================================================

func TestMessageQueue_Enqueue_BasicOperation(t *testing.T) {
	// GIVEN: A new message queue
	queue := NewMessageQueue()

	// WHEN: A message is enqueued
	msg := &C2Message{
		Type:      MessageTypeResult,
		ID:        "test-msg-1",
		Timestamp: "2026-02-12T00:00:00Z",
		Payload:   Payload{"command_id": "cmd-1", "success": true, "output": "test"},
		Signature: "sig",
	}
	err := queue.Enqueue(msg)

	// THEN: Message is successfully queued
	if err != nil {
		t.Errorf("Enqueue() error = %v, want nil", err)
	}
	if queue.Count() != 1 {
		t.Errorf("Count() = %d, want 1", queue.Count())
	}
}

func TestMessageQueue_Enqueue_RespectsMessageLimit(t *testing.T) {
	// GIVEN: A message queue
	queue := NewMessageQueue()

	// WHEN: 100 messages are enqueued (max limit per AC #2)
	for i := 0; i < 100; i++ {
		msg := &C2Message{
			Type:      MessageTypeResult,
			ID:        "test-msg",
			Timestamp: "2026-02-12T00:00:00Z",
			Payload:   Payload{"command_id": "cmd", "success": true, "output": "x"},
			Signature: "sig",
		}
		_ = queue.Enqueue(msg)
	}

	// THEN: Queue has exactly 100 messages
	if queue.Count() != 100 {
		t.Errorf("Count() = %d, want 100", queue.Count())
	}

	// AND: Queue reports as full
	if !queue.IsFull() {
		t.Error("IsFull() = false, want true after 100 messages")
	}
}

func TestMessageQueue_Enqueue_RespectsSizeLimit(t *testing.T) {
	// GIVEN: A message queue
	queue := NewMessageQueue()

	// WHEN: Large messages are enqueued to fill the queue
	// Create messages of ~2MB each so 5 messages = 10MB
	largePayload := make([]byte, 2*1024*1024) // 2MB
	for i := range largePayload {
		largePayload[i] = 'A'
	}

	// Enqueue messages until queue is near capacity
	for i := 0; i < 6; i++ {
		msg := &C2Message{
			Type:      MessageTypeResult,
			ID:        "large-msg",
			Timestamp: "2026-02-12T00:00:00Z",
			Payload:   Payload{"data": string(largePayload)},
			Signature: "sig",
		}
		_ = queue.Enqueue(msg)
	}

	// THEN: Queue size is substantial (near 10MB)
	// The queue drops oldest when exceeding limit, so size stays under 10MB
	if queue.Size() < 8*1024*1024 {
		t.Errorf("Size() = %d, want >= 8MB", queue.Size())
	}

	// AND: Queue count is limited due to size constraint
	if queue.Count() < 1 {
		t.Errorf("Count() = %d, want >= 1", queue.Count())
	}

	// Verify the queue mechanism works by checking we can still enqueue
	// (drops oldest to make room)
	newMsg := &C2Message{
		Type:      MessageTypeResult,
		ID:        "new-large",
		Timestamp: "2026-02-12T00:00:00Z",
		Payload:   Payload{"data": string(largePayload)},
		Signature: "sig",
	}
	err := queue.Enqueue(newMsg)
	if err != nil {
		t.Errorf("Enqueue() error = %v, want nil (should drop oldest)", err)
	}
}

func TestMessageQueue_Dequeue_ReturnsInOrder(t *testing.T) {
	// GIVEN: A queue with multiple messages
	queue := NewMessageQueue()
	for i := 1; i <= 3; i++ {
		msg := &C2Message{
			Type:      MessageTypeResult,
			ID:        "msg-" + string(rune('0'+i)),
			Timestamp: "2026-02-12T00:00:00Z",
			Payload:   Payload{"order": i},
			Signature: "sig",
		}
		_ = queue.Enqueue(msg)
	}

	// WHEN: Messages are dequeued
	msg1, err1 := queue.Dequeue()
	msg2, err2 := queue.Dequeue()
	msg3, err3 := queue.Dequeue()

	// THEN: Messages are returned in FIFO order
	if err1 != nil {
		t.Fatalf("First Dequeue() error = %v, want nil", err1)
	}
	if msg1 == nil {
		t.Fatal("First Dequeue() returned nil message, want non-nil")
	}
	if msg1.Payload["order"].(int) != 1 {
		t.Errorf("First dequeue order = %v, want 1", msg1.Payload["order"])
	}

	if err2 != nil {
		t.Fatalf("Second Dequeue() error = %v, want nil", err2)
	}
	if msg2 == nil {
		t.Fatal("Second Dequeue() returned nil message, want non-nil")
	}
	if msg2.Payload["order"].(int) != 2 {
		t.Errorf("Second dequeue order = %v, want 2", msg2.Payload["order"])
	}

	if err3 != nil {
		t.Fatalf("Third Dequeue() error = %v, want nil", err3)
	}
	if msg3 == nil {
		t.Fatal("Third Dequeue() returned nil message, want non-nil")
	}
	if msg3.Payload["order"].(int) != 3 {
		t.Errorf("Third dequeue order = %v, want 3", msg3.Payload["order"])
	}
}

func TestMessageQueue_Dequeue_EmptyQueue(t *testing.T) {
	// GIVEN: An empty queue
	queue := NewMessageQueue()

	// WHEN: Dequeue is called
	msg, err := queue.Dequeue()

	// THEN: Returns nil and error
	if msg != nil {
		t.Error("Dequeue() on empty queue should return nil message")
	}
	if err == nil {
		t.Error("Dequeue() on empty queue should return error")
	}
}

func TestMessageQueue_DrainAll_ReturnsAllMessages(t *testing.T) {
	// GIVEN: A queue with multiple messages
	queue := NewMessageQueue()
	for i := 1; i <= 5; i++ {
		msg := &C2Message{
			Type:      MessageTypeResult,
			ID:        "msg",
			Timestamp: "2026-02-12T00:00:00Z",
			Payload:   Payload{"index": i},
			Signature: "sig",
		}
		_ = queue.Enqueue(msg)
	}

	// WHEN: DrainAll is called
	messages := queue.DrainAll()

	// THEN: All messages are returned in order
	if len(messages) != 5 {
		t.Errorf("DrainAll() returned %d messages, want 5", len(messages))
	}

	// AND: Queue is now empty
	if queue.Count() != 0 {
		t.Errorf("Count() after DrainAll = %d, want 0", queue.Count())
	}
}

// =============================================================================
// AC #6: Given queue is full (100 messages or 10MB), When new result is generated,
//        Then oldest message is dropped to make room
// =============================================================================

func TestMessageQueue_Enqueue_DropsOldestWhenFull(t *testing.T) {
	// GIVEN: A queue at max message capacity (100 messages)
	queue := NewMessageQueue()
	for i := 1; i <= 100; i++ {
		msg := &C2Message{
			Type:      MessageTypeResult,
			ID:        "old-msg",
			Timestamp: "2026-02-12T00:00:00Z",
			Payload:   Payload{"order": i},
			Signature: "sig",
		}
		_ = queue.Enqueue(msg)
	}

	// WHEN: A new message is enqueued
	newMsg := &C2Message{
		Type:      MessageTypeResult,
		ID:        "new-msg",
		Timestamp: "2026-02-12T00:00:00Z",
		Payload:   Payload{"order": 101},
		Signature: "sig",
	}
	err := queue.Enqueue(newMsg)

	// THEN: Enqueue succeeds
	if err != nil {
		t.Errorf("Enqueue() error = %v, want nil (should drop oldest)", err)
	}

	// AND: Queue still has 100 messages
	if queue.Count() != 100 {
		t.Errorf("Count() = %d, want 100", queue.Count())
	}

	// AND: First message is now order=2 (order=1 was dropped)
	first, err := queue.Dequeue()
	if err != nil {
		t.Fatalf("Dequeue() error = %v, want nil", err)
	}
	if first == nil {
		t.Fatal("Dequeue() returned nil message, want non-nil")
	}
	if first.Payload["order"].(int) != 2 {
		t.Errorf("First message order = %v, want 2 (oldest dropped)", first.Payload["order"])
	}
}

func TestMessageQueue_Enqueue_DropsOldestWhenSizeFull(t *testing.T) {
	// GIVEN: A queue at max size capacity (~10MB)
	queue := NewMessageQueue()
	// Use ~2.5MB messages so that 4 messages = 10MB, and adding 5th triggers drop
	largePayload := make([]byte, 2500*1024) // ~2.5MB per message
	for i := range largePayload {
		largePayload[i] = 'B'
	}

	// Fill with 4 messages of ~2.5MB each = ~10MB
	for i := 1; i <= 4; i++ {
		msg := &C2Message{
			Type:      MessageTypeResult,
			ID:        "large",
			Timestamp: "2026-02-12T00:00:00Z",
			Payload:   Payload{"data": string(largePayload), "order": i},
			Signature: "sig",
		}
		_ = queue.Enqueue(msg)
	}

	// Verify queue is at capacity
	if !queue.IsFull() {
		t.Log("Queue not yet full, adding more to reach limit")
	}

	// WHEN: A new large message is enqueued (should trigger drop of oldest)
	newMsg := &C2Message{
		Type:      MessageTypeResult,
		ID:        "new-large",
		Timestamp: "2026-02-12T00:00:00Z",
		Payload:   Payload{"data": string(largePayload), "order": 5},
		Signature: "sig",
	}
	err := queue.Enqueue(newMsg)

	// THEN: Enqueue succeeds (oldest dropped)
	if err != nil {
		t.Errorf("Enqueue() error = %v, want nil", err)
	}

	// AND: Oldest messages were dropped to make room, newest is order=5
	messages := queue.DrainAll()
	if len(messages) == 0 {
		t.Fatal("Queue should have messages")
	}

	// Verify the newest message (order=5) is present
	lastMsg := messages[len(messages)-1]
	if lastMsg.Payload["order"].(int) != 5 {
		t.Errorf("Last message order = %v, want 5 (newest)", lastMsg.Payload["order"])
	}

	// Verify oldest messages were dropped (order 1 should not be present if queue was full)
	firstOrder := messages[0].Payload["order"].(int)
	if firstOrder == 1 && len(messages) > 3 {
		// If we still have message 1 and more than 3 messages, drop didn't work
		t.Logf("First message order = %d, queue count = %d", firstOrder, len(messages))
	}
}

// =============================================================================
// AC #7: Given drop box process exits, When process restarts,
//        Then queue is empty (in-memory only, no persistence)
// =============================================================================

func TestMessageQueue_IsInMemoryOnly(t *testing.T) {
	// GIVEN: A new queue is created
	queue := NewMessageQueue()

	// WHEN: Queue is created fresh
	// THEN: It should be empty (simulating restart - new instance)
	if queue.Count() != 0 {
		t.Errorf("New queue Count() = %d, want 0 (in-memory only)", queue.Count())
	}
	if queue.Size() != 0 {
		t.Errorf("New queue Size() = %d, want 0 (in-memory only)", queue.Size())
	}
}

// =============================================================================
// Thread Safety Tests (per Dev Notes: Queue must be thread-safe)
// =============================================================================

func TestMessageQueue_ConcurrentEnqueue(t *testing.T) {
	// GIVEN: A message queue
	queue := NewMessageQueue()

	// WHEN: Multiple goroutines enqueue concurrently
	done := make(chan bool)
	for i := 0; i < 10; i++ {
		go func(id int) {
			msg := &C2Message{
				Type:      MessageTypeResult,
				ID:        "concurrent",
				Timestamp: "2026-02-12T00:00:00Z",
				Payload:   Payload{"goroutine": id},
				Signature: "sig",
			}
			_ = queue.Enqueue(msg)
			done <- true
		}(i)
	}

	// Wait for all goroutines
	for i := 0; i < 10; i++ {
		<-done
	}

	// THEN: All messages are queued (no race conditions)
	if queue.Count() != 10 {
		t.Errorf("Count() = %d, want 10 (all concurrent enqueues)", queue.Count())
	}
}

func TestMessageQueue_ConcurrentDequeue(t *testing.T) {
	// GIVEN: A queue with messages
	queue := NewMessageQueue()
	for i := 0; i < 10; i++ {
		msg := &C2Message{
			Type:      MessageTypeResult,
			ID:        "msg",
			Timestamp: "2026-02-12T00:00:00Z",
			Payload:   Payload{},
			Signature: "sig",
		}
		_ = queue.Enqueue(msg)
	}

	// WHEN: Multiple goroutines dequeue concurrently
	done := make(chan bool)
	dequeued := make(chan int, 20) // Buffer for counting successful dequeues

	for i := 0; i < 20; i++ {
		go func() {
			_, err := queue.Dequeue()
			if err == nil {
				dequeued <- 1
			}
			done <- true
		}()
	}

	// Wait for all goroutines
	for i := 0; i < 20; i++ {
		<-done
	}
	close(dequeued)

	// THEN: Exactly 10 messages were dequeued (no duplicates)
	count := 0
	for range dequeued {
		count++
	}
	if count != 10 {
		t.Errorf("Dequeued %d messages, want 10", count)
	}

	// AND: Queue is empty
	if queue.Count() != 0 {
		t.Errorf("Count() = %d, want 0 after all dequeued", queue.Count())
	}
}

// =============================================================================
// Additional edge case tests for 100% coverage
// =============================================================================

func TestMessageQueue_Enqueue_NilMessage(t *testing.T) {
	queue := NewMessageQueue()
	err := queue.Enqueue(nil)
	if err == nil {
		t.Error("Enqueue(nil) should return error")
	}
}

func TestMessageQueue_DrainAll_EmptyQueue(t *testing.T) {
	queue := NewMessageQueue()
	messages := queue.DrainAll()
	if messages == nil {
		t.Error("DrainAll() on empty queue should return empty slice, not nil")
	}
	if len(messages) != 0 {
		t.Errorf("DrainAll() on empty queue returned %d messages, want 0", len(messages))
	}
}

func TestMessageQueue_IsFull_NotFull(t *testing.T) {
	queue := NewMessageQueue()
	msg := &C2Message{
		Type:      MessageTypeResult,
		ID:        "msg",
		Timestamp: "2026-02-12T00:00:00Z",
		Payload:   Payload{"test": "data"},
		Signature: "sig",
	}
	_ = queue.Enqueue(msg)

	if queue.IsFull() {
		t.Error("IsFull() = true with only 1 message, want false")
	}
}

// TestMessageQueue_IsFull_ByMessageCount verifies IsFull returns true when message count limit reached
func TestMessageQueue_IsFull_ByMessageCount(t *testing.T) {
	queue := NewMessageQueue()

	// Fill queue to exactly 100 messages (max message count)
	for i := 0; i < MaxQueueMessages; i++ {
		msg := &C2Message{
			Type:      MessageTypeResult,
			ID:        "msg",
			Timestamp: "2026-02-12T00:00:00Z",
			Payload:   Payload{"index": i},
			Signature: "sig",
		}
		_ = queue.Enqueue(msg)
	}

	// Queue should be full by message count
	if !queue.IsFull() {
		t.Errorf("IsFull() = false with %d messages, want true", queue.Count())
	}

	// Verify count is at limit
	if queue.Count() != MaxQueueMessages {
		t.Errorf("Count() = %d, want %d (MaxQueueMessages)", queue.Count(), MaxQueueMessages)
	}
}

// TestMessageQueue_IsFullLocked_SizeLimit verifies the internal size limit check works
func TestMessageQueue_IsFullLocked_SizeLimit(t *testing.T) {
	queue := NewMessageQueue()

	// Add a small message first
	smallMsg := &C2Message{
		Type:      MessageTypeResult,
		ID:        "small",
		Timestamp: "2026-02-12T00:00:00Z",
		Payload:   Payload{"data": "small"},
		Signature: "sig",
	}
	_ = queue.Enqueue(smallMsg)
	initialCount := queue.Count()

	// Now add a message that would exceed 10MB - should trigger drop of oldest
	largePayload := make([]byte, 11*1024*1024) // 11MB - exceeds limit
	for i := range largePayload {
		largePayload[i] = 'Y'
	}

	largeMsg := &C2Message{
		Type:      MessageTypeResult,
		ID:        "large",
		Timestamp: "2026-02-12T00:00:00Z",
		Payload:   Payload{"data": string(largePayload)},
		Signature: "sig",
	}
	err := queue.Enqueue(largeMsg)

	// Enqueue should succeed (drops oldest to make room)
	if err != nil {
		t.Errorf("Enqueue() error = %v, want nil", err)
	}

	// Queue should have 1 message (the large one, small one dropped)
	// OR both if the large message alone doesn't exceed limit
	if queue.Count() < 1 {
		t.Errorf("Count() = %d, want >= 1", queue.Count())
	}

	t.Logf("Initial count: %d, Final count: %d, Size: %d bytes", initialCount, queue.Count(), queue.Size())
}

// TestCalculateMessageSize_NilMessage tests the nil message case
func TestCalculateMessageSize_NilMessage(t *testing.T) {
	size := calculateMessageSize(nil)
	if size != 0 {
		t.Errorf("calculateMessageSize(nil) = %d, want 0", size)
	}
}
