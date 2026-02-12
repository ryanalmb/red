// Package c2 provides the mTLS WebSocket client for C2 communication.
// This file implements the MessageQueue for Story 12.11: Drop Box Reconnection Handling
package c2

import (
	"encoding/json"
	"errors"
	"sync"
	"time"
)

// ReconnectionTimeout is the maximum time to attempt reconnection before
// resetting the backoff cycle (per NFR17 and AC #5).
const ReconnectionTimeout = 30 * time.Second

// MaxQueueMessages is the maximum number of messages in the queue (per AC #2).
const MaxQueueMessages = 100

// MaxQueueSize is the maximum total size of queued messages in bytes (per AC #2).
// 10MB = 10 * 1024 * 1024 bytes
const MaxQueueSize int64 = 10 * 1024 * 1024

// ErrQueueEmpty is returned when attempting to dequeue from an empty queue.
var ErrQueueEmpty = errors.New("queue is empty")

// queueEntry holds a message and its serialized size for efficient size tracking.
type queueEntry struct {
	msg  *C2Message
	size int64
}

// MessageQueue provides thread-safe message queueing for pending results
// during C2 disconnection. Per Story 12.11, the queue:
// - Stores up to 100 messages OR 10MB total (whichever is reached first)
// - Drops oldest messages when full
// - Is in-memory only (no persistence)
type MessageQueue struct {
	mu        sync.Mutex
	messages  []queueEntry
	totalSize int64
}

// NewMessageQueue creates a new empty MessageQueue.
// The queue is in-memory only and starts empty (AC #7).
func NewMessageQueue() *MessageQueue {
	return &MessageQueue{
		messages:  make([]queueEntry, 0),
		totalSize: 0,
	}
}

// calculateMessageSize returns the approximate size of a C2Message in bytes.
func calculateMessageSize(msg *C2Message) int64 {
	if msg == nil {
		return 0
	}
	// Serialize to JSON to get accurate size
	data, err := json.Marshal(msg)
	if err != nil {
		// Fallback: estimate based on fields
		return 1024 // Default estimate
	}
	return int64(len(data))
}

// Enqueue adds a message to the queue.
// If the queue is full (100 messages or 10MB), the oldest message is dropped (AC #6).
// Thread-safe per Dev Notes.
func (q *MessageQueue) Enqueue(msg *C2Message) error {
	if msg == nil {
		return errors.New("cannot enqueue nil message")
	}

	q.mu.Lock()
	defer q.mu.Unlock()

	msgSize := calculateMessageSize(msg)
	entry := queueEntry{msg: msg, size: msgSize}

	// Drop oldest messages while queue is full (AC #6)
	// Check both message count limit and size limit
	for q.isFullLocked(msgSize) && len(q.messages) > 0 {
		// Remove oldest message
		oldest := q.messages[0]
		q.messages = q.messages[1:]
		q.totalSize -= oldest.size
	}

	// Add the new message
	q.messages = append(q.messages, entry)
	q.totalSize += msgSize

	return nil
}

// isFullLocked checks if queue is full (must hold lock).
// Takes the size of the message being added to check if it would exceed limits.
func (q *MessageQueue) isFullLocked(additionalSize int64) bool {
	// Check message count limit
	if len(q.messages) >= MaxQueueMessages {
		return true
	}
	// Check size limit - queue is full if adding this message would exceed limit
	// AND we already have messages (so we can drop one to make room)
	if len(q.messages) > 0 && q.totalSize+additionalSize > MaxQueueSize {
		return true
	}
	return false
}

// Dequeue removes and returns the oldest message from the queue.
// Returns an error if the queue is empty.
// Thread-safe per Dev Notes.
func (q *MessageQueue) Dequeue() (*C2Message, error) {
	q.mu.Lock()
	defer q.mu.Unlock()

	if len(q.messages) == 0 {
		return nil, ErrQueueEmpty
	}

	// Remove and return oldest message (FIFO)
	entry := q.messages[0]
	q.messages = q.messages[1:]
	q.totalSize -= entry.size

	return entry.msg, nil
}

// DrainAll removes and returns all messages from the queue in order.
// The queue will be empty after this call.
// Thread-safe per Dev Notes.
func (q *MessageQueue) DrainAll() []*C2Message {
	q.mu.Lock()
	defer q.mu.Unlock()

	if len(q.messages) == 0 {
		return []*C2Message{}
	}

	// Extract all messages
	result := make([]*C2Message, len(q.messages))
	for i, entry := range q.messages {
		result[i] = entry.msg
	}

	// Clear the queue
	q.messages = make([]queueEntry, 0)
	q.totalSize = 0

	return result
}

// Count returns the number of messages currently in the queue.
func (q *MessageQueue) Count() int {
	q.mu.Lock()
	defer q.mu.Unlock()
	return len(q.messages)
}

// Size returns the total size of all messages in the queue in bytes.
func (q *MessageQueue) Size() int64 {
	q.mu.Lock()
	defer q.mu.Unlock()
	return q.totalSize
}

// IsFull returns true if the queue has reached its capacity limits
// (100 messages or 10MB total size).
func (q *MessageQueue) IsFull() bool {
	q.mu.Lock()
	defer q.mu.Unlock()
	return len(q.messages) >= MaxQueueMessages || q.totalSize >= MaxQueueSize
}
