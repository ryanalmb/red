// Package abort provides drop box abort and wipe functionality.
//
// Story 12.10: Drop Box Abort & Wipe
// Per FR30: Operator can send abort/wipe command to any drop box
// Per ERR4: Drop box connection loss — wipe proceeds anyway (fail-safe)
//
// Security: Sensitive files are overwritten with random data before deletion
// to prevent forensic recovery.
package abort

import (
	"context"
	"crypto/rand"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/cyber-red/dropbox/internal"
)

// AbortReason represents why the abort was triggered.
type AbortReason string

const (
	// ReasonOperatorInitiated is a normal operator-triggered abort.
	ReasonOperatorInitiated AbortReason = "operator_initiated"
	// ReasonCompromised indicates drop box suspected to be compromised.
	ReasonCompromised AbortReason = "compromised"
	// ReasonEngagementEnded indicates the engagement has concluded.
	ReasonEngagementEnded AbortReason = "engagement_ended"
	// ReasonEmergency is an emergency abort (fastest path).
	ReasonEmergency AbortReason = "emergency"
)

// WipeStatus represents the status of the wipe operation.
type WipeStatus string

const (
	// WipeSuccess indicates all sensitive files wiped successfully.
	WipeSuccess WipeStatus = "success"
	// WipePartial indicates some files wiped, some failed.
	WipePartial WipeStatus = "partial"
	// WipeFailed indicates wipe failed completely.
	WipeFailed WipeStatus = "failed"
	// WipeInProgress indicates wipe is currently executing.
	WipeInProgress WipeStatus = "in_progress"
)

// AbortCommand represents an abort command from the C2 server.
type AbortCommand struct {
	Reason       AbortReason `json:"reason"`
	DeleteBinary bool        `json:"delete_binary"`
}

// WipeResult contains the result of a wipe operation.
type WipeResult struct {
	Status      WipeStatus `json:"status"`
	FilesWiped  int        `json:"files_wiped"`
	FilesFailed int        `json:"files_failed"`
	Errors      []string   `json:"errors"`
	DurationMS  int64      `json:"duration_ms"`
}

// AbortResult contains the overall result of an abort operation.
type AbortResult struct {
	WipeResult           *WipeResult `json:"wipe_result"`
	SelfDestructInitiated bool       `json:"self_destruct_initiated"`
}

// Handler manages abort and wipe operations.
type Handler struct {
	mu            sync.Mutex
	sensitiveDir  string // Directory containing sensitive files
	binaryPath    string // Path to the drop box binary
	cancelFuncs   []context.CancelFunc
	logger        *internal.Logger
}

// NewHandler creates a new abort handler.
func NewHandler(sensitiveDir, binaryPath string, logger *internal.Logger) *Handler {
	return &Handler{
		sensitiveDir: sensitiveDir,
		binaryPath:   binaryPath,
		logger:       logger,
	}
}

// RegisterCancelFunc registers a cancel function for stopping operations.
func (h *Handler) RegisterCancelFunc(cancel context.CancelFunc) {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.cancelFuncs = append(h.cancelFuncs, cancel)
}

// HandleAbort processes an abort command.
// It stops all operations, wipes sensitive files, and initiates self-destruct.
func (h *Handler) HandleAbort(cmd AbortCommand) AbortResult {
	h.logger.Info("abort_received: reason=%s delete_binary=%v", string(cmd.Reason), cmd.DeleteBinary)

	// Step 1: Stop all operations immediately (AC#2)
	h.StopAllOperations()

	// Step 2: Execute secure wipe (AC#3)
	wipeResult := h.SecureWipe()

	// Step 3: Self-destruct (AC#4)
	selfDestructInitiated := h.SelfDestruct(cmd.DeleteBinary)

	return AbortResult{
		WipeResult:           wipeResult,
		SelfDestructInitiated: selfDestructInitiated,
	}
}

// StopAllOperations cancels all running contexts and stops command processing.
// Per AC#2: Drop box stops all operations immediately.
func (h *Handler) StopAllOperations() {
	h.mu.Lock()
	defer h.mu.Unlock()

	h.logger.Info("stopping_all_operations: cancel_funcs=%d", len(h.cancelFuncs))

	for _, cancel := range h.cancelFuncs {
		cancel()
	}
	h.cancelFuncs = nil
}

// SecureWipe overwrites and deletes all sensitive files.
// Per AC#3: Files are overwritten with random data before deletion.
func (h *Handler) SecureWipe() *WipeResult {
	start := time.Now()

	paths := h.GetSensitiveFilePaths()
	h.logger.Info("secure_wipe_started: file_count=%d", len(paths))

	var (
		wiped   int
		failed  int
		errors  []string
	)

	for _, path := range paths {
		if err := SecureWipeFile(path); err != nil {
			failed++
			errors = append(errors, fmt.Sprintf("%s: %v", path, err))
			h.logger.Warn("secure_wipe_file_failed: path=%s error=%v", path, err)
		} else {
			wiped++
			h.logger.Debug("secure_wipe_file_success: path=%s", path)
		}
	}

	durationMS := time.Since(start).Milliseconds()

	status := WipeSuccess
	if failed > 0 && wiped > 0 {
		status = WipePartial
	} else if failed > 0 && wiped == 0 {
		status = WipeFailed
	}

	h.logger.Info("secure_wipe_completed: status=%s wiped=%d failed=%d duration_ms=%d",
		string(status), wiped, failed, durationMS)

	return &WipeResult{
		Status:      status,
		FilesWiped:  wiped,
		FilesFailed: failed,
		Errors:      errors,
		DurationMS:  durationMS,
	}
}

// GetSensitiveFilePaths returns paths to certs, logs, cache, and config.
func (h *Handler) GetSensitiveFilePaths() []string {
	var paths []string

	// Sensitive file patterns
	patterns := []string{
		"*.crt", "*.pem", "*.key",  // Certificates
		"*.log",                     // Logs
		"*.db", "*.cache",           // Cache/database
		"config.yaml", "config.json", // Config
	}

	for _, pattern := range patterns {
		matches, err := filepath.Glob(filepath.Join(h.sensitiveDir, pattern))
		if err != nil {
			h.logger.Warn("glob_pattern_failed: pattern=%s error=%v", pattern, err)
			continue
		}
		paths = append(paths, matches...)
	}

	return paths
}

// SelfDestruct exits the process and optionally deletes the binary.
// Per AC#4: Drop box process exits cleanly, optionally removes binary.
func (h *Handler) SelfDestruct(deleteBinary bool) bool {
	h.logger.Info("self_destruct_initiated: delete_binary=%v", deleteBinary)

	if deleteBinary && h.binaryPath != "" {
		// Schedule binary deletion after process exit
		// We can't delete a running binary on some OSes, so we try our best
		if err := os.Remove(h.binaryPath); err != nil {
			h.logger.Warn("binary_delete_failed: path=%s error=%v", h.binaryPath, err)
			// Continue with exit anyway
		} else {
			h.logger.Info("binary_deleted: path=%s", h.binaryPath)
		}
	}

	// Exit is deferred to allow the caller to send the result back to C2
	// The actual os.Exit() should be called by the main process
	return true
}

// SecureWipeFile overwrites a file with random data before deletion.
// Per architecture security requirements:
// 1. Overwrite with random data (crypto-grade)
// 2. Sync to disk
// 3. Delete the file
func SecureWipeFile(path string) error {
	info, err := os.Stat(path)
	if err != nil {
		return fmt.Errorf("stat failed: %w", err)
	}

	// Skip directories
	if info.IsDir() {
		return nil
	}

	// Open file for writing
	f, err := os.OpenFile(path, os.O_WRONLY, 0)
	if err != nil {
		return fmt.Errorf("open failed: %w", err)
	}

	// Overwrite with random data
	size := info.Size()
	randomData := make([]byte, size)
	if _, err := rand.Read(randomData); err != nil {
		f.Close()
		return fmt.Errorf("random read failed: %w", err)
	}

	if _, err := f.Write(randomData); err != nil {
		f.Close()
		return fmt.Errorf("write failed: %w", err)
	}

	// Sync to ensure data is written to disk
	if err := f.Sync(); err != nil {
		f.Close()
		return fmt.Errorf("sync failed: %w", err)
	}

	f.Close()

	// Now delete the file
	if err := os.Remove(path); err != nil {
		return fmt.Errorf("remove failed: %w", err)
	}

	return nil
}
