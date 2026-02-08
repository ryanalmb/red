package c2

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestDefaultConstants(t *testing.T) {
	tests := []struct {
		name     string
		got      interface{}
		expected interface{}
	}{
		{"DefaultServerPort", DefaultServerPort, 8444},
		{"DefaultHeartbeatInterval", DefaultHeartbeatInterval, 5 * time.Second},
		{"DefaultConnectionTimeout", DefaultConnectionTimeout, 30 * time.Second},
		{"DefaultReconnectDelay", DefaultReconnectDelay, 1 * time.Second},
		{"DefaultMaxReconnectDelay", DefaultMaxReconnectDelay, 30 * time.Second}, // Changed per AC #2
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if tt.got != tt.expected {
				t.Errorf("%s = %v, want %v", tt.name, tt.got, tt.expected)
			}
		})
	}
}

func TestNewConfig(t *testing.T) {
	cfg := NewConfig()

	if cfg == nil {
		t.Fatal("NewConfig returned nil")
	}
	if cfg.HeartbeatInterval != DefaultHeartbeatInterval {
		t.Errorf("HeartbeatInterval = %v, want %v", cfg.HeartbeatInterval, DefaultHeartbeatInterval)
	}
	if cfg.ConnectionTimeout != DefaultConnectionTimeout {
		t.Errorf("ConnectionTimeout = %v, want %v", cfg.ConnectionTimeout, DefaultConnectionTimeout)
	}
	if cfg.ReconnectDelay != DefaultReconnectDelay {
		t.Errorf("ReconnectDelay = %v, want %v", cfg.ReconnectDelay, DefaultReconnectDelay)
	}
	if cfg.MaxReconnectDelay != DefaultMaxReconnectDelay {
		t.Errorf("MaxReconnectDelay = %v, want %v", cfg.MaxReconnectDelay, DefaultMaxReconnectDelay)
	}
}

func TestConfigValidate(t *testing.T) {
	tests := []struct {
		name      string
		config    *Config
		wantError string
	}{
		{
			name:      "missing server address",
			config:    &Config{CertFile: "cert.pem", KeyFile: "key.pem", CAFile: "ca.pem", HeartbeatInterval: time.Second, ConnectionTimeout: time.Second},
			wantError: "server address is required",
		},
		{
			name:      "missing cert file",
			config:    &Config{ServerAddress: "localhost:8444", KeyFile: "key.pem", CAFile: "ca.pem", HeartbeatInterval: time.Second, ConnectionTimeout: time.Second},
			wantError: "client certificate file is required",
		},
		{
			name:      "missing key file",
			config:    &Config{ServerAddress: "localhost:8444", CertFile: "cert.pem", CAFile: "ca.pem", HeartbeatInterval: time.Second, ConnectionTimeout: time.Second},
			wantError: "client key file is required",
		},
		{
			name:      "missing CA file",
			config:    &Config{ServerAddress: "localhost:8444", CertFile: "cert.pem", KeyFile: "key.pem", HeartbeatInterval: time.Second, ConnectionTimeout: time.Second},
			wantError: "CA certificate file is required",
		},
		{
			name:      "invalid heartbeat interval",
			config:    &Config{ServerAddress: "localhost:8444", CertFile: "cert.pem", KeyFile: "key.pem", CAFile: "ca.pem", HeartbeatInterval: 0, ConnectionTimeout: time.Second},
			wantError: "heartbeat interval must be positive",
		},
		{
			name:      "negative heartbeat interval",
			config:    &Config{ServerAddress: "localhost:8444", CertFile: "cert.pem", KeyFile: "key.pem", CAFile: "ca.pem", HeartbeatInterval: -time.Second, ConnectionTimeout: time.Second},
			wantError: "heartbeat interval must be positive",
		},
		{
			name:      "invalid connection timeout",
			config:    &Config{ServerAddress: "localhost:8444", CertFile: "cert.pem", KeyFile: "key.pem", CAFile: "ca.pem", HeartbeatInterval: time.Second, ConnectionTimeout: 0},
			wantError: "connection timeout must be positive",
		},
		{
			name:      "valid config with files",
			config:    &Config{ServerAddress: "localhost:8444", CertFile: "cert.pem", KeyFile: "key.pem", CAFile: "ca.pem", HeartbeatInterval: time.Second, ConnectionTimeout: time.Second},
			wantError: "",
		},
		{
			name:      "valid config with embedded PEM",
			config:    &Config{ServerAddress: "localhost:8444", CertPEM: "cert-data", KeyPEM: "key-data", CAPEM: "ca-data", HeartbeatInterval: time.Second, ConnectionTimeout: time.Second},
			wantError: "",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.config.Validate()
			if tt.wantError == "" {
				if err != nil {
					t.Errorf("Validate() error = %v, want nil", err)
				}
			} else {
				if err == nil {
					t.Errorf("Validate() error = nil, want %q", tt.wantError)
				} else if err.Error() != tt.wantError {
					t.Errorf("Validate() error = %q, want %q", err.Error(), tt.wantError)
				}
			}
		})
	}
}

func TestConfigFromFile(t *testing.T) {
	// Create temp directory for test files
	tmpDir := t.TempDir()

	t.Run("file not found", func(t *testing.T) {
		_, err := ConfigFromFile("/nonexistent/config.yaml")
		if err == nil {
			t.Error("ConfigFromFile() should error on missing file")
		}
	})

	t.Run("invalid yaml", func(t *testing.T) {
		path := filepath.Join(tmpDir, "invalid.yaml")
		os.WriteFile(path, []byte("not: valid: yaml: {{"), 0644)

		_, err := ConfigFromFile(path)
		if err == nil {
			t.Error("ConfigFromFile() should error on invalid YAML")
		}
	})

	t.Run("valid config with defaults", func(t *testing.T) {
		path := filepath.Join(tmpDir, "minimal.yaml")
		yaml := `
server_address: "c2.example.com:8444"
cert_file: "/path/to/cert.pem"
key_file: "/path/to/key.pem"
ca_file: "/path/to/ca.pem"
shared_secret: "super-secret"
drop_box_id: "dropbox-001"
`
		os.WriteFile(path, []byte(yaml), 0644)

		cfg, err := ConfigFromFile(path)
		if err != nil {
			t.Fatalf("ConfigFromFile() error: %v", err)
		}

		if cfg.ServerAddress != "c2.example.com:8444" {
			t.Errorf("ServerAddress = %s, want c2.example.com:8444", cfg.ServerAddress)
		}
		if cfg.SharedSecret != "super-secret" {
			t.Errorf("SharedSecret = %s, want super-secret", cfg.SharedSecret)
		}
		if cfg.DropBoxID != "dropbox-001" {
			t.Errorf("DropBoxID = %s, want dropbox-001", cfg.DropBoxID)
		}
		// Check defaults were applied
		if cfg.HeartbeatInterval != DefaultHeartbeatInterval {
			t.Errorf("HeartbeatInterval = %v, want %v", cfg.HeartbeatInterval, DefaultHeartbeatInterval)
		}
		if cfg.ConnectionTimeout != DefaultConnectionTimeout {
			t.Errorf("ConnectionTimeout = %v, want %v", cfg.ConnectionTimeout, DefaultConnectionTimeout)
		}
		if cfg.MaxReconnectDelay != DefaultMaxReconnectDelay {
			t.Errorf("MaxReconnectDelay = %v, want %v", cfg.MaxReconnectDelay, DefaultMaxReconnectDelay)
		}
	})

	t.Run("valid config with custom durations", func(t *testing.T) {
		path := filepath.Join(tmpDir, "custom.yaml")
		yaml := `
server_address: "localhost:8444"
cert_file: "/path/to/cert.pem"
key_file: "/path/to/key.pem"
ca_file: "/path/to/ca.pem"
heartbeat_interval: "10s"
connection_timeout: "60s"
reconnect_delay: "2s"
max_reconnect_delay: "30s"
insecure_skip_verify: true
`
		os.WriteFile(path, []byte(yaml), 0644)

		cfg, err := ConfigFromFile(path)
		if err != nil {
			t.Fatalf("ConfigFromFile() error: %v", err)
		}

		if cfg.HeartbeatInterval != 10*time.Second {
			t.Errorf("HeartbeatInterval = %v, want 10s", cfg.HeartbeatInterval)
		}
		if cfg.ConnectionTimeout != 60*time.Second {
			t.Errorf("ConnectionTimeout = %v, want 60s", cfg.ConnectionTimeout)
		}
		if cfg.ReconnectDelay != 2*time.Second {
			t.Errorf("ReconnectDelay = %v, want 2s", cfg.ReconnectDelay)
		}
		if cfg.MaxReconnectDelay != 30*time.Second {
			t.Errorf("MaxReconnectDelay = %v, want 30s", cfg.MaxReconnectDelay)
		}
		if !cfg.InsecureSkipVerify {
			t.Error("InsecureSkipVerify should be true")
		}
	})

	t.Run("embedded PEM support", func(t *testing.T) {
		path := filepath.Join(tmpDir, "embedded.yaml")
		yaml := `
server_address: "localhost:8444"
cert_pem: |
  -----BEGIN CERTIFICATE-----
  MIICert...
  -----END CERTIFICATE-----
key_pem: |
  -----BEGIN PRIVATE KEY-----
  MIIKey...
  -----END PRIVATE KEY-----
ca_pem: |
  -----BEGIN CERTIFICATE-----
  MIICA...
  -----END CERTIFICATE-----
`
		os.WriteFile(path, []byte(yaml), 0644)

		cfg, err := ConfigFromFile(path)
		if err != nil {
			t.Fatalf("ConfigFromFile() error: %v", err)
		}

		if cfg.CertPEM == "" {
			t.Error("CertPEM should not be empty")
		}
		if cfg.KeyPEM == "" {
			t.Error("KeyPEM should not be empty")
		}
		if cfg.CAPEM == "" {
			t.Error("CAPEM should not be empty")
		}
	})

	t.Run("invalid duration", func(t *testing.T) {
		path := filepath.Join(tmpDir, "bad_duration.yaml")
		yaml := `
server_address: "localhost:8444"
cert_file: "/path/to/cert.pem"
key_file: "/path/to/key.pem"
ca_file: "/path/to/ca.pem"
heartbeat_interval: "not-a-duration"
`
		os.WriteFile(path, []byte(yaml), 0644)

		_, err := ConfigFromFile(path)
		if err == nil {
			t.Error("ConfigFromFile() should error on invalid duration")
		}
		if err.Error() != "invalid heartbeat_interval duration" {
			t.Errorf("Error = %q, want 'invalid heartbeat_interval duration'", err.Error())
		}
	})
}
