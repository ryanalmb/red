package internal

import (
	"bytes"
	"strings"
	"testing"
)

func TestLogLevelString(t *testing.T) {
	tests := []struct {
		level    LogLevel
		expected string
	}{
		{LogLevelDebug, "DEBUG"},
		{LogLevelInfo, "INFO"},
		{LogLevelWarn, "WARN"},
		{LogLevelError, "ERROR"},
		{LogLevel(99), "UNKNOWN"},
	}

	for _, tt := range tests {
		t.Run(tt.expected, func(t *testing.T) {
			if got := tt.level.String(); got != tt.expected {
				t.Errorf("LogLevel.String() = %v, want %v", got, tt.expected)
			}
		})
	}
}

func TestNewLogger(t *testing.T) {
	logger := NewLogger(LogLevelInfo)
	if logger == nil {
		t.Fatal("NewLogger returned nil")
	}
	if logger.minLevel != LogLevelInfo {
		t.Errorf("minLevel = %v, want %v", logger.minLevel, LogLevelInfo)
	}
}

func TestLoggerSetOutput(t *testing.T) {
	logger := NewLogger(LogLevelInfo)
	var buf bytes.Buffer
	logger.SetOutput(&buf)

	logger.Info("test message")

	output := buf.String()
	if !strings.Contains(output, "test message") {
		t.Errorf("Expected output to contain 'test message', got: %s", output)
	}
	if !strings.Contains(output, "[INFO]") {
		t.Errorf("Expected output to contain '[INFO]', got: %s", output)
	}
}

func TestLoggerSetLevel(t *testing.T) {
	logger := NewLogger(LogLevelError)
	var buf bytes.Buffer
	logger.SetOutput(&buf)

	// This should not be logged (Info < Error)
	logger.Info("should not appear")

	if buf.Len() > 0 {
		t.Errorf("Info message should not be logged when level is Error")
	}

	// Change level to Debug
	logger.SetLevel(LogLevelDebug)
	logger.Debug("should appear")

	if !strings.Contains(buf.String(), "should appear") {
		t.Errorf("Debug message should be logged after SetLevel(Debug)")
	}
}

func TestLoggerLevels(t *testing.T) {
	tests := []struct {
		name      string
		minLevel  LogLevel
		logFunc   func(*Logger, string, ...interface{})
		logLevel  string
		shouldLog bool
	}{
		{"Debug at Debug level", LogLevelDebug, (*Logger).Debug, "DEBUG", true},
		{"Info at Debug level", LogLevelDebug, (*Logger).Info, "INFO", true},
		{"Warn at Debug level", LogLevelDebug, (*Logger).Warn, "WARN", true},
		{"Error at Debug level", LogLevelDebug, (*Logger).Error, "ERROR", true},
		{"Debug at Info level", LogLevelInfo, (*Logger).Debug, "DEBUG", false},
		{"Info at Info level", LogLevelInfo, (*Logger).Info, "INFO", true},
		{"Warn at Info level", LogLevelInfo, (*Logger).Warn, "WARN", true},
		{"Error at Info level", LogLevelInfo, (*Logger).Error, "ERROR", true},
		{"Debug at Warn level", LogLevelWarn, (*Logger).Debug, "DEBUG", false},
		{"Info at Warn level", LogLevelWarn, (*Logger).Info, "INFO", false},
		{"Warn at Warn level", LogLevelWarn, (*Logger).Warn, "WARN", true},
		{"Error at Warn level", LogLevelWarn, (*Logger).Error, "ERROR", true},
		{"Debug at Error level", LogLevelError, (*Logger).Debug, "DEBUG", false},
		{"Info at Error level", LogLevelError, (*Logger).Info, "INFO", false},
		{"Warn at Error level", LogLevelError, (*Logger).Warn, "WARN", false},
		{"Error at Error level", LogLevelError, (*Logger).Error, "ERROR", true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			logger := NewLogger(tt.minLevel)
			var buf bytes.Buffer
			logger.SetOutput(&buf)

			tt.logFunc(logger, "test message")

			hasOutput := buf.Len() > 0
			if hasOutput != tt.shouldLog {
				t.Errorf("shouldLog = %v, but hasOutput = %v", tt.shouldLog, hasOutput)
			}
			if tt.shouldLog && !strings.Contains(buf.String(), tt.logLevel) {
				t.Errorf("Expected log level %s in output: %s", tt.logLevel, buf.String())
			}
		})
	}
}

func TestLoggerFormatting(t *testing.T) {
	logger := NewLogger(LogLevelDebug)
	var buf bytes.Buffer
	logger.SetOutput(&buf)

	logger.Info("user %s logged in with id %d", "alice", 42)

	output := buf.String()
	if !strings.Contains(output, "user alice logged in with id 42") {
		t.Errorf("Expected formatted message, got: %s", output)
	}
}

func TestLoggerTimestamp(t *testing.T) {
	logger := NewLogger(LogLevelInfo)
	var buf bytes.Buffer
	logger.SetOutput(&buf)

	logger.Info("test")

	output := buf.String()
	// Check for RFC3339 timestamp format (contains T and Z or +/-)
	if !strings.Contains(output, "T") || (!strings.Contains(output, "Z") && !strings.Contains(output, "+") && !strings.Contains(output, "-")) {
		t.Errorf("Expected RFC3339 timestamp in output: %s", output)
	}
}

func TestDefaultLogger(t *testing.T) {
	if DefaultLogger == nil {
		t.Fatal("DefaultLogger should not be nil")
	}
}

func TestPackageLevelFunctions(t *testing.T) {
	// Save original output
	var buf bytes.Buffer
	originalOutput := DefaultLogger.output
	DefaultLogger.SetOutput(&buf)
	DefaultLogger.SetLevel(LogLevelDebug)
	defer func() {
		DefaultLogger.SetOutput(originalOutput)
		DefaultLogger.SetLevel(LogLevelInfo)
	}()

	// Test package-level functions
	Debug("debug %s", "msg")
	Info("info %s", "msg")
	Warn("warn %s", "msg")
	Error("error %s", "msg")

	output := buf.String()
	if !strings.Contains(output, "debug msg") {
		t.Error("Debug() did not log")
	}
	if !strings.Contains(output, "info msg") {
		t.Error("Info() did not log")
	}
	if !strings.Contains(output, "warn msg") {
		t.Error("Warn() did not log")
	}
	if !strings.Contains(output, "error msg") {
		t.Error("Error() did not log")
	}
}
