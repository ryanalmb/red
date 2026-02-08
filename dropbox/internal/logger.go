// Package internal provides shared utilities for the drop box binary.
package internal

import (
	"fmt"
	"io"
	"os"
	"sync"
	"time"
)

// LogLevel represents the severity of a log message.
type LogLevel int

const (
	// LogLevelDebug is for detailed debugging information.
	LogLevelDebug LogLevel = iota
	// LogLevelInfo is for general informational messages.
	LogLevelInfo
	// LogLevelWarn is for warning conditions.
	LogLevelWarn
	// LogLevelError is for error conditions.
	LogLevelError
)

// String returns the string representation of the log level.
func (l LogLevel) String() string {
	switch l {
	case LogLevelDebug:
		return "DEBUG"
	case LogLevelInfo:
		return "INFO"
	case LogLevelWarn:
		return "WARN"
	case LogLevelError:
		return "ERROR"
	default:
		return "UNKNOWN"
	}
}

// Logger provides structured logging for the drop box.
type Logger struct {
	mu       sync.Mutex
	output   io.Writer
	minLevel LogLevel
}

// NewLogger creates a new Logger with the specified minimum level.
func NewLogger(minLevel LogLevel) *Logger {
	return &Logger{
		output:   os.Stderr,
		minLevel: minLevel,
	}
}

// SetOutput sets the output destination for the logger.
func (l *Logger) SetOutput(w io.Writer) {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.output = w
}

// SetLevel sets the minimum log level.
func (l *Logger) SetLevel(level LogLevel) {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.minLevel = level
}

// log writes a log message if the level is at or above the minimum level.
func (l *Logger) log(level LogLevel, format string, args ...interface{}) {
	l.mu.Lock()
	defer l.mu.Unlock()

	if level < l.minLevel {
		return
	}

	timestamp := time.Now().UTC().Format(time.RFC3339)
	message := fmt.Sprintf(format, args...)
	fmt.Fprintf(l.output, "%s [%s] %s\n", timestamp, level.String(), message)
}

// Debug logs a debug message.
func (l *Logger) Debug(format string, args ...interface{}) {
	l.log(LogLevelDebug, format, args...)
}

// Info logs an informational message.
func (l *Logger) Info(format string, args ...interface{}) {
	l.log(LogLevelInfo, format, args...)
}

// Warn logs a warning message.
func (l *Logger) Warn(format string, args ...interface{}) {
	l.log(LogLevelWarn, format, args...)
}

// Error logs an error message.
func (l *Logger) Error(format string, args ...interface{}) {
	l.log(LogLevelError, format, args...)
}

// DefaultLogger is the default logger instance.
var DefaultLogger = NewLogger(LogLevelInfo)

// Debug logs a debug message using the default logger.
func Debug(format string, args ...interface{}) {
	DefaultLogger.Debug(format, args...)
}

// Info logs an informational message using the default logger.
func Info(format string, args ...interface{}) {
	DefaultLogger.Info(format, args...)
}

// Warn logs a warning message using the default logger.
func Warn(format string, args ...interface{}) {
	DefaultLogger.Warn(format, args...)
}

// Error logs an error message using the default logger.
func Error(format string, args ...interface{}) {
	DefaultLogger.Error(format, args...)
}
