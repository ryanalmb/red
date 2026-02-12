// Package c2 provides the mTLS WebSocket client for C2 communication.
// This package implements the client-side of the C2 protocol defined in Story 12.2.
package c2

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"os"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

// Connection state constants
type ConnectionState int

const (
	// StateDisconnected indicates no active connection.
	StateDisconnected ConnectionState = iota
	// StateConnecting indicates connection is being established.
	StateConnecting
	// StateConnected indicates an active connection.
	StateConnected
	// StateReconnecting indicates reconnection is in progress.
	StateReconnecting
)

func (s ConnectionState) String() string {
	switch s {
	case StateDisconnected:
		return "disconnected"
	case StateConnecting:
		return "connecting"
	case StateConnected:
		return "connected"
	case StateReconnecting:
		return "reconnecting"
	default:
		return "unknown"
	}
}

// Backoff delays for reconnection attempts (per AC #2)
var backoffDelays = []time.Duration{
	1 * time.Second,
	2 * time.Second,
	4 * time.Second,
	8 * time.Second,
	16 * time.Second,
	30 * time.Second, // Max per AC #2
}

// Client represents an mTLS WebSocket client for C2 communication.
type Client struct {
	config *Config

	// Connection state
	conn     *websocket.Conn
	state    ConnectionState
	stateMu  sync.RWMutex
	attempt  int // Current reconnection attempt

	// Control channels
	ctx        context.Context
	cancel     context.CancelFunc
	heartbeatC chan struct{}
	commandC   chan *C2Message
	errC       chan error

	// TLS configuration (cached after first load)
	tlsConfig *tls.Config
	tlsMu     sync.Mutex

	// Shared secret for message signing
	sharedSecret []byte

	// Drop box identity
	dropBoxID string

	// Story 12.11: Message queue for pending results during disconnect
	messageQueue *MessageQueue

	// Story 12.11: Track reconnection start time for 30s timeout (AC #5)
	reconnectStartTime time.Time
}

// NewClient creates a new C2 client with the provided configuration.
func NewClient(cfg *Config) (*Client, error) {
	if cfg == nil {
		return nil, errors.New("config cannot be nil")
	}
	return &Client{
		config:       cfg,
		state:        StateDisconnected,
		commandC:     make(chan *C2Message, 10),
		errC:         make(chan error, 1),
		messageQueue: NewMessageQueue(), // Story 12.11: Initialize message queue
	}, nil
}

// SetSharedSecret sets the shared secret for HMAC-SHA256 signing.
// Makes a defensive copy to prevent external modification.
func (c *Client) SetSharedSecret(secret []byte) {
	if secret == nil {
		c.sharedSecret = nil
		return
	}
	c.sharedSecret = make([]byte, len(secret))
	copy(c.sharedSecret, secret)
}

// SetDropBoxID sets the drop box identifier for heartbeat messages.
func (c *Client) SetDropBoxID(id string) {
	c.dropBoxID = id
}

// State returns the current connection state.
func (c *Client) State() ConnectionState {
	c.stateMu.RLock()
	defer c.stateMu.RUnlock()
	return c.state
}

func (c *Client) setState(state ConnectionState) {
	c.stateMu.Lock()
	defer c.stateMu.Unlock()
	c.state = state
}

// loadTLSConfig loads and caches the TLS configuration.
// Supports both file paths (CertFile, KeyFile, CAFile) and embedded PEM (CertPEM, KeyPEM, CAPEM).
func (c *Client) loadTLSConfig() (*tls.Config, error) {
	c.tlsMu.Lock()
	defer c.tlsMu.Unlock()

	if c.tlsConfig != nil {
		return c.tlsConfig, nil
	}

	var cert tls.Certificate
	var err error

	// Load client certificate - prefer embedded PEM over file paths
	if c.config.CertPEM != "" && c.config.KeyPEM != "" {
		cert, err = tls.X509KeyPair([]byte(c.config.CertPEM), []byte(c.config.KeyPEM))
		if err != nil {
			return nil, fmt.Errorf("failed to parse embedded certificate: %w", err)
		}
	} else if c.config.CertFile != "" && c.config.KeyFile != "" {
		cert, err = tls.LoadX509KeyPair(c.config.CertFile, c.config.KeyFile)
		if err != nil {
			return nil, fmt.Errorf("failed to load client certificate: %w", err)
		}
	} else {
		return nil, errors.New("no client certificate provided (need CertFile/KeyFile or CertPEM/KeyPEM)")
	}

	// Load CA certificate - prefer embedded PEM over file path
	var caCert []byte
	if c.config.CAPEM != "" {
		caCert = []byte(c.config.CAPEM)
	} else if c.config.CAFile != "" {
		caCert, err = os.ReadFile(c.config.CAFile)
		if err != nil {
			return nil, fmt.Errorf("failed to read CA certificate: %w", err)
		}
	} else {
		return nil, errors.New("no CA certificate provided (need CAFile or CAPEM)")
	}

	caCertPool := x509.NewCertPool()
	if !caCertPool.AppendCertsFromPEM(caCert) {
		return nil, errors.New("failed to parse CA certificate")
	}

	// Extract server name from address for SNI
	serverName := c.config.ServerAddress
	if u, err := url.Parse("wss://" + c.config.ServerAddress); err == nil && u.Hostname() != "" {
		serverName = u.Hostname()
	}

	c.tlsConfig = &tls.Config{
		Certificates:       []tls.Certificate{cert},
		RootCAs:            caCertPool,
		MinVersion:         tls.VersionTLS12,
		ServerName:         serverName,
		InsecureSkipVerify: c.config.InsecureSkipVerify,
	}

	return c.tlsConfig, nil
}

// Connect establishes an mTLS WebSocket connection to the C2 server.
func (c *Client) Connect() error {
	c.setState(StateConnecting)

	// Load TLS configuration
	tlsConfig, err := c.loadTLSConfig()
	if err != nil {
		c.setState(StateDisconnected)
		return err
	}

	// Create WebSocket dialer with mTLS
	dialer := websocket.Dialer{
		TLSClientConfig:  tlsConfig,
		HandshakeTimeout: c.config.ConnectionTimeout,
	}

	// Build WebSocket URL
	wsURL := fmt.Sprintf("wss://%s/ws", c.config.ServerAddress)

	// Attempt connection
	conn, _, err := dialer.Dial(wsURL, nil)
	if err != nil {
		c.setState(StateDisconnected)
		return fmt.Errorf("failed to connect: %w", err)
	}

	c.conn = conn
	c.attempt = 0 // Reset reconnection attempts on successful connect
	c.setState(StateConnected)

	// Create context for goroutines
	c.ctx, c.cancel = context.WithCancel(context.Background())
	c.heartbeatC = make(chan struct{})

	// Start background goroutines
	go c.readLoop()
	go c.heartbeatLoop()

	return nil
}

// Disconnect closes the connection to the C2 server.
func (c *Client) Disconnect() error {
	if c.cancel != nil {
		c.cancel()
	}

	c.stateMu.Lock()
	defer c.stateMu.Unlock()

	if c.conn != nil {
		// Send close message
		_ = c.conn.WriteMessage(
			websocket.CloseMessage,
			websocket.FormatCloseMessage(websocket.CloseNormalClosure, ""),
		)
		err := c.conn.Close()
		c.conn = nil
		c.state = StateDisconnected
		return err
	}

	c.state = StateDisconnected
	return nil
}

// readLoop reads messages from the WebSocket connection.
func (c *Client) readLoop() {
	for {
		select {
		case <-c.ctx.Done():
			return
		default:
			_, data, err := c.conn.ReadMessage()
			if err != nil {
				if websocket.IsUnexpectedCloseError(err, websocket.CloseNormalClosure, websocket.CloseGoingAway) {
					select {
					case c.errC <- err:
					default:
					}
				}
				c.handleDisconnect()
				return
			}

			// Parse message
			msg, err := ParseMessage(data)
			if err != nil {
				continue // Skip invalid messages
			}

			// Verify signature if we have a shared secret
			if len(c.sharedSecret) > 0 {
				valid, _ := VerifySignature(msg, c.sharedSecret)
				if !valid {
					continue // Skip messages with invalid signatures
				}
			}

			// Only queue command messages for ReceiveCommand()
			if msg.Type == MessageTypeCommand {
				select {
				case c.commandC <- msg:
				default:
					// Command channel full, drop oldest
					select {
					case <-c.commandC:
					default:
					}
					c.commandC <- msg
				}
			}
		}
	}
}

// heartbeatLoop sends periodic heartbeat messages.
func (c *Client) heartbeatLoop() {
	ticker := time.NewTicker(c.config.HeartbeatInterval)
	defer ticker.Stop()

	for {
		select {
		case <-c.ctx.Done():
			return
		case <-ticker.C:
			if err := c.SendHeartbeat(); err != nil {
				c.handleDisconnect()
				return
			}
		case <-c.heartbeatC:
			// Manual heartbeat trigger (for testing)
			if err := c.SendHeartbeat(); err != nil {
				c.handleDisconnect()
				return
			}
		}
	}
}

// handleDisconnect handles connection loss and triggers reconnection.
func (c *Client) handleDisconnect() {
	if c.State() == StateReconnecting {
		return // Already reconnecting
	}
	c.setState(StateReconnecting)

	// Story 12.11: Track when reconnection started for 30s timeout (AC #5)
	c.reconnectStartTime = time.Now()

	go c.reconnectLoop()
}

// reconnectLoop attempts to reconnect with exponential backoff.
func (c *Client) reconnectLoop() {
	for {
		select {
		case <-c.ctx.Done():
			c.setState(StateDisconnected)
			return
		default:
			// Story 12.11 AC #5: Check if 30s timeout passed and reset backoff cycle
			c.checkAndResetBackoffCycle()

			// Calculate backoff delay
			delay := c.getBackoffDelay()
			c.attempt++

			time.Sleep(delay)

			// Attempt reconnection
			if c.conn != nil {
				_ = c.conn.Close()
				c.conn = nil
			}

			// Load TLS configuration
			tlsConfig, err := c.loadTLSConfig()
			if err != nil {
				continue
			}

			dialer := websocket.Dialer{
				TLSClientConfig:  tlsConfig,
				HandshakeTimeout: c.config.ConnectionTimeout,
			}

			wsURL := fmt.Sprintf("wss://%s/ws", c.config.ServerAddress)
			conn, _, err := dialer.Dial(wsURL, nil)
			if err != nil {
				continue // Keep trying
			}

			c.conn = conn
			c.attempt = 0
			c.reconnectStartTime = time.Time{} // Clear reconnection tracking
			c.setState(StateConnected)

			// Story 12.11 AC #3: Drain queued messages after successful reconnection
			_ = c.drainQueue()

			// Restart read loop
			go c.readLoop()
			return
		}
	}
}

// getBackoffDelay returns the backoff delay for the current attempt.
func (c *Client) getBackoffDelay() time.Duration {
	if c.attempt >= len(backoffDelays) {
		return backoffDelays[len(backoffDelays)-1]
	}
	return backoffDelays[c.attempt]
}

// SendHeartbeat sends a heartbeat message to the C2 server.
// Per Story 12.4, heartbeats are sent every 5 seconds.
func (c *Client) SendHeartbeat() error {
	if c.State() != StateConnected {
		return errors.New("not connected")
	}

	if len(c.sharedSecret) == 0 {
		return errors.New("shared secret not set")
	}

	status := "active"
	msg, err := NewHeartbeatMessage(c.dropBoxID, status, c.sharedSecret)
	if err != nil {
		return fmt.Errorf("failed to create heartbeat: %w", err)
	}

	data, err := msg.ToJSON()
	if err != nil {
		return fmt.Errorf("failed to serialize heartbeat: %w", err)
	}

	c.stateMu.RLock()
	conn := c.conn
	c.stateMu.RUnlock()

	if conn == nil {
		return errors.New("connection is nil")
	}

	return conn.WriteMessage(websocket.TextMessage, data)
}

// SendResult sends a command result to the C2 server.
// Per Story 12.11 AC #2: If disconnected, queues the result locally.
func (c *Client) SendResult(commandID string, result []byte) error {
	if len(c.sharedSecret) == 0 {
		return errors.New("shared secret not set")
	}

	// Parse result as JSON if possible, otherwise use string
	var output any
	if err := json.Unmarshal(result, &output); err != nil {
		output = string(result)
	}

	msg, err := NewResultMessage(commandID, true, output, c.sharedSecret)
	if err != nil {
		return fmt.Errorf("failed to create result message: %w", err)
	}

	// Story 12.11 AC #2: Queue results when disconnected
	if c.State() != StateConnected {
		if c.messageQueue != nil {
			return c.messageQueue.Enqueue(msg)
		}
		return errors.New("not connected")
	}

	data, err := msg.ToJSON()
	if err != nil {
		return fmt.Errorf("failed to serialize result: %w", err)
	}

	c.stateMu.RLock()
	conn := c.conn
	c.stateMu.RUnlock()

	if conn == nil {
		// Queue the message if connection is nil but state says connected
		if c.messageQueue != nil {
			return c.messageQueue.Enqueue(msg)
		}
		return errors.New("connection is nil")
	}

	return conn.WriteMessage(websocket.TextMessage, data)
}

// ReceiveCommand waits for and returns the next command from the C2 server.
func (c *Client) ReceiveCommand() ([]byte, error) {
	// Handle case where client is not connected (no context)
	if c.ctx == nil {
		return nil, errors.New("client not connected")
	}

	select {
	case msg := <-c.commandC:
		return msg.ToJSON()
	case err := <-c.errC:
		return nil, err
	case <-c.ctx.Done():
		return nil, errors.New("client disconnected")
	}
}

// drainQueue sends all queued messages after successful reconnection (Story 12.11 AC #3).
func (c *Client) drainQueue() error {
	if c.messageQueue == nil {
		return nil
	}

	if c.State() != StateConnected {
		return errors.New("cannot drain queue: not connected")
	}

	messages := c.messageQueue.DrainAll()
	if len(messages) == 0 {
		return nil
	}

	c.stateMu.RLock()
	conn := c.conn
	c.stateMu.RUnlock()

	if conn == nil {
		// Re-queue messages if connection lost during drain
		for _, msg := range messages {
			_ = c.messageQueue.Enqueue(msg)
		}
		return errors.New("connection lost during drain")
	}

	// Send all queued messages in order (AC #3)
	for _, msg := range messages {
		data, err := msg.ToJSON()
		if err != nil {
			continue // Skip messages that fail to serialize
		}
		if err := conn.WriteMessage(websocket.TextMessage, data); err != nil {
			// Re-queue remaining messages on failure
			return fmt.Errorf("failed to send queued message: %w", err)
		}
	}

	return nil
}

// checkAndResetBackoffCycle checks if 30s timeout has passed and resets backoff (Story 12.11 AC #5).
func (c *Client) checkAndResetBackoffCycle() {
	if c.reconnectStartTime.IsZero() {
		return
	}

	// If we've been reconnecting for more than ReconnectionTimeout (30s), reset the cycle
	if time.Since(c.reconnectStartTime) > ReconnectionTimeout {
		c.attempt = 0
		c.reconnectStartTime = time.Now() // Start a new cycle
	}
}

// ReceiveCommandWithTimeout waits for a command with a timeout.
func (c *Client) ReceiveCommandWithTimeout(timeout time.Duration) ([]byte, error) {
	// Handle case where client is not connected (no context)
	if c.ctx == nil {
		select {
		case msg := <-c.commandC:
			return msg.ToJSON()
		case err := <-c.errC:
			return nil, err
		case <-time.After(timeout):
			return nil, errors.New("timeout waiting for command")
		}
	}

	select {
	case msg := <-c.commandC:
		return msg.ToJSON()
	case err := <-c.errC:
		return nil, err
	case <-time.After(timeout):
		return nil, errors.New("timeout waiting for command")
	case <-c.ctx.Done():
		return nil, errors.New("client disconnected")
	}
}
