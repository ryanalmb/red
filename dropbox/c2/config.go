// Package c2 provides the mTLS WebSocket client for C2 communication.
package c2

import (
	"errors"
	"os"
	"time"

	"gopkg.in/yaml.v3"
)

// Default configuration values per Story 12.1-12.4.
const (
	// DefaultServerPort is the default C2 server port (per Story 12.1).
	DefaultServerPort = 8444

	// DefaultHeartbeatInterval is the interval between heartbeats (per Story 12.4).
	DefaultHeartbeatInterval = 5 * time.Second

	// DefaultConnectionTimeout is the timeout for initial connection.
	DefaultConnectionTimeout = 30 * time.Second

	// DefaultReconnectDelay is the initial delay before reconnection attempts.
	DefaultReconnectDelay = 1 * time.Second

	// DefaultMaxReconnectDelay is the maximum delay between reconnection attempts.
	// Per AC #2: max 30s (not 60s as originally defined)
	DefaultMaxReconnectDelay = 30 * time.Second
)

// Config holds the configuration for the C2 client.
type Config struct {
	// ServerAddress is the address of the C2 server (host:port).
	ServerAddress string `yaml:"server_address"`

	// CertFile is the path to the client certificate file.
	CertFile string `yaml:"cert_file"`

	// KeyFile is the path to the client private key file.
	KeyFile string `yaml:"key_file"`

	// CAFile is the path to the CA certificate file for server verification.
	CAFile string `yaml:"ca_file"`

	// CertPEM is the client certificate in PEM format (alternative to CertFile).
	CertPEM string `yaml:"cert_pem"`

	// KeyPEM is the client private key in PEM format (alternative to KeyFile).
	KeyPEM string `yaml:"key_pem"`

	// CAPEM is the CA certificate in PEM format (alternative to CAFile).
	CAPEM string `yaml:"ca_pem"`

	// SharedSecret is the shared secret for HMAC-SHA256 signing.
	// ⚠️  SECURITY WARNING: Never log this value!
	SharedSecret string `yaml:"shared_secret"`

	// DropBoxID is the unique identifier for this drop box.
	DropBoxID string `yaml:"drop_box_id"`

	// HeartbeatInterval is the interval between heartbeat messages.
	HeartbeatInterval time.Duration `yaml:"heartbeat_interval"`

	// ConnectionTimeout is the timeout for establishing connections.
	ConnectionTimeout time.Duration `yaml:"connection_timeout"`

	// ReconnectDelay is the initial delay before reconnection attempts.
	ReconnectDelay time.Duration `yaml:"reconnect_delay"`

	// MaxReconnectDelay is the maximum delay between reconnection attempts.
	MaxReconnectDelay time.Duration `yaml:"max_reconnect_delay"`

	// InsecureSkipVerify disables server certificate verification.
	// ⚠️  SECURITY WARNING: This should ONLY be used for local testing!
	// Enabling this in production defeats the purpose of mTLS and exposes
	// the connection to man-in-the-middle attacks. The C2 client will log
	// a warning when this is enabled.
	InsecureSkipVerify bool `yaml:"insecure_skip_verify"`
}

// configYAML is an intermediate struct for YAML parsing with string durations.
type configYAML struct {
	ServerAddress      string `yaml:"server_address"`
	CertFile           string `yaml:"cert_file"`
	KeyFile            string `yaml:"key_file"`
	CAFile             string `yaml:"ca_file"`
	CertPEM            string `yaml:"cert_pem"`
	KeyPEM             string `yaml:"key_pem"`
	CAPEM              string `yaml:"ca_pem"`
	SharedSecret       string `yaml:"shared_secret"`
	DropBoxID          string `yaml:"drop_box_id"`
	HeartbeatInterval  string `yaml:"heartbeat_interval"`
	ConnectionTimeout  string `yaml:"connection_timeout"`
	ReconnectDelay     string `yaml:"reconnect_delay"`
	MaxReconnectDelay  string `yaml:"max_reconnect_delay"`
	InsecureSkipVerify bool   `yaml:"insecure_skip_verify"`
}

// NewConfig creates a new Config with default values.
func NewConfig() *Config {
	return &Config{
		HeartbeatInterval: DefaultHeartbeatInterval,
		ConnectionTimeout: DefaultConnectionTimeout,
		ReconnectDelay:    DefaultReconnectDelay,
		MaxReconnectDelay: DefaultMaxReconnectDelay,
	}
}

// Validate checks that the configuration is valid.
func (c *Config) Validate() error {
	if c.ServerAddress == "" {
		return errors.New("server address is required")
	}
	// Check for either file path or embedded PEM
	if c.CertFile == "" && c.CertPEM == "" {
		return errors.New("client certificate file is required")
	}
	if c.KeyFile == "" && c.KeyPEM == "" {
		return errors.New("client key file is required")
	}
	if c.CAFile == "" && c.CAPEM == "" {
		return errors.New("CA certificate file is required")
	}
	if c.HeartbeatInterval <= 0 {
		return errors.New("heartbeat interval must be positive")
	}
	if c.ConnectionTimeout <= 0 {
		return errors.New("connection timeout must be positive")
	}
	return nil
}

// ConfigFromFile loads configuration from a YAML file.
// Supports both file paths for certificates and embedded PEM content.
func ConfigFromFile(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	var yamlCfg configYAML
	if err := yaml.Unmarshal(data, &yamlCfg); err != nil {
		return nil, err
	}

	cfg := &Config{
		ServerAddress:      yamlCfg.ServerAddress,
		CertFile:           yamlCfg.CertFile,
		KeyFile:            yamlCfg.KeyFile,
		CAFile:             yamlCfg.CAFile,
		CertPEM:            yamlCfg.CertPEM,
		KeyPEM:             yamlCfg.KeyPEM,
		CAPEM:              yamlCfg.CAPEM,
		SharedSecret:       yamlCfg.SharedSecret,
		DropBoxID:          yamlCfg.DropBoxID,
		InsecureSkipVerify: yamlCfg.InsecureSkipVerify,
	}

	// Parse duration fields with defaults
	if yamlCfg.HeartbeatInterval != "" {
		d, err := time.ParseDuration(yamlCfg.HeartbeatInterval)
		if err != nil {
			return nil, errors.New("invalid heartbeat_interval duration")
		}
		cfg.HeartbeatInterval = d
	} else {
		cfg.HeartbeatInterval = DefaultHeartbeatInterval
	}

	if yamlCfg.ConnectionTimeout != "" {
		d, err := time.ParseDuration(yamlCfg.ConnectionTimeout)
		if err != nil {
			return nil, errors.New("invalid connection_timeout duration")
		}
		cfg.ConnectionTimeout = d
	} else {
		cfg.ConnectionTimeout = DefaultConnectionTimeout
	}

	if yamlCfg.ReconnectDelay != "" {
		d, err := time.ParseDuration(yamlCfg.ReconnectDelay)
		if err != nil {
			return nil, errors.New("invalid reconnect_delay duration")
		}
		cfg.ReconnectDelay = d
	} else {
		cfg.ReconnectDelay = DefaultReconnectDelay
	}

	if yamlCfg.MaxReconnectDelay != "" {
		d, err := time.ParseDuration(yamlCfg.MaxReconnectDelay)
		if err != nil {
			return nil, errors.New("invalid max_reconnect_delay duration")
		}
		cfg.MaxReconnectDelay = d
	} else {
		cfg.MaxReconnectDelay = DefaultMaxReconnectDelay
	}

	return cfg, nil
}
