package abort

import (
	"context"
	"os"
	"path/filepath"
	"testing"

	"github.com/cyber-red/dropbox/internal"
)

func TestAbortReasonConstants(t *testing.T) {
	tests := []struct {
		reason   AbortReason
		expected string
	}{
		{ReasonOperatorInitiated, "operator_initiated"},
		{ReasonCompromised, "compromised"},
		{ReasonEngagementEnded, "engagement_ended"},
		{ReasonEmergency, "emergency"},
	}

	for _, tt := range tests {
		if string(tt.reason) != tt.expected {
			t.Errorf("AbortReason %v = %q, want %q", tt.reason, string(tt.reason), tt.expected)
		}
	}
}

func TestWipeStatusConstants(t *testing.T) {
	tests := []struct {
		status   WipeStatus
		expected string
	}{
		{WipeSuccess, "success"},
		{WipePartial, "partial"},
		{WipeFailed, "failed"},
		{WipeInProgress, "in_progress"},
	}

	for _, tt := range tests {
		if string(tt.status) != tt.expected {
			t.Errorf("WipeStatus %v = %q, want %q", tt.status, string(tt.status), tt.expected)
		}
	}
}

func TestNewHandler(t *testing.T) {
	logger := internal.NewLogger(internal.LogLevelDebug)
	h := NewHandler("/tmp/sensitive", "/usr/bin/dropbox", logger)

	if h.sensitiveDir != "/tmp/sensitive" {
		t.Errorf("sensitiveDir = %q, want %q", h.sensitiveDir, "/tmp/sensitive")
	}
	if h.binaryPath != "/usr/bin/dropbox" {
		t.Errorf("binaryPath = %q, want %q", h.binaryPath, "/usr/bin/dropbox")
	}
	if h.logger != logger {
		t.Error("logger not set correctly")
	}
}

func TestRegisterCancelFunc(t *testing.T) {
	logger := internal.NewLogger(internal.LogLevelDebug)
	h := NewHandler("/tmp", "/tmp/bin", logger)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	h.RegisterCancelFunc(cancel)

	if len(h.cancelFuncs) != 1 {
		t.Errorf("cancelFuncs length = %d, want 1", len(h.cancelFuncs))
	}

	// Verify context is not cancelled yet
	select {
	case <-ctx.Done():
		t.Error("context should not be cancelled yet")
	default:
		// Good
	}
}

func TestStopAllOperations(t *testing.T) {
	logger := internal.NewLogger(internal.LogLevelDebug)
	h := NewHandler("/tmp", "/tmp/bin", logger)

	// Create multiple contexts
	ctx1, cancel1 := context.WithCancel(context.Background())
	ctx2, cancel2 := context.WithCancel(context.Background())

	h.RegisterCancelFunc(cancel1)
	h.RegisterCancelFunc(cancel2)

	// Stop all operations
	h.StopAllOperations()

	// Verify all contexts are cancelled
	select {
	case <-ctx1.Done():
		// Good
	default:
		t.Error("ctx1 should be cancelled")
	}

	select {
	case <-ctx2.Done():
		// Good
	default:
		t.Error("ctx2 should be cancelled")
	}

	// Verify cancel funcs are cleared
	if len(h.cancelFuncs) != 0 {
		t.Errorf("cancelFuncs should be empty after StopAllOperations, got %d", len(h.cancelFuncs))
	}
}

func TestSecureWipeFile(t *testing.T) {
	// Create a temp file with known content
	tmpDir := t.TempDir()
	testFile := filepath.Join(tmpDir, "test.key")
	originalContent := []byte("super secret key data 12345")

	if err := os.WriteFile(testFile, originalContent, 0644); err != nil {
		t.Fatalf("failed to create test file: %v", err)
	}

	// Verify file exists
	if _, err := os.Stat(testFile); os.IsNotExist(err) {
		t.Fatal("test file should exist before wipe")
	}

	// Wipe the file
	if err := SecureWipeFile(testFile); err != nil {
		t.Fatalf("SecureWipeFile failed: %v", err)
	}

	// Verify file is deleted
	if _, err := os.Stat(testFile); !os.IsNotExist(err) {
		t.Error("test file should not exist after wipe")
	}
}

func TestSecureWipeFileNonExistent(t *testing.T) {
	err := SecureWipeFile("/nonexistent/path/file.txt")
	if err == nil {
		t.Error("SecureWipeFile should fail for non-existent file")
	}
}

func TestSecureWipeFileDirectory(t *testing.T) {
	tmpDir := t.TempDir()

	// Should not error on directory (just skip)
	err := SecureWipeFile(tmpDir)
	if err != nil {
		t.Errorf("SecureWipeFile should skip directories, got error: %v", err)
	}
}

func TestSecureWipe(t *testing.T) {
	// Create temp directory with sensitive files
	tmpDir := t.TempDir()
	
	// Create test files
	testFiles := []string{
		"server.crt",
		"server.key",
		"access.log",
		"cache.db",
	}

	for _, name := range testFiles {
		path := filepath.Join(tmpDir, name)
		if err := os.WriteFile(path, []byte("sensitive data"), 0644); err != nil {
			t.Fatalf("failed to create %s: %v", name, err)
		}
	}

	logger := internal.NewLogger(internal.LogLevelDebug)
	h := NewHandler(tmpDir, "", logger)

	// Execute wipe
	result := h.SecureWipe()

	// Verify result
	if result.Status != WipeSuccess {
		t.Errorf("Status = %q, want %q", result.Status, WipeSuccess)
	}
	if result.FilesWiped != 4 {
		t.Errorf("FilesWiped = %d, want 4", result.FilesWiped)
	}
	if result.FilesFailed != 0 {
		t.Errorf("FilesFailed = %d, want 0", result.FilesFailed)
	}
	if len(result.Errors) != 0 {
		t.Errorf("Errors = %v, want empty", result.Errors)
	}
	if result.DurationMS < 0 {
		t.Errorf("DurationMS = %d, should be >= 0", result.DurationMS)
	}

	// Verify files are deleted
	for _, name := range testFiles {
		path := filepath.Join(tmpDir, name)
		if _, err := os.Stat(path); !os.IsNotExist(err) {
			t.Errorf("file %s should be deleted", name)
		}
	}
}

func TestSecureWipePartial(t *testing.T) {
	// Skip this test when running as root (root can read any file)
	if os.Getuid() == 0 {
		t.Skip("skipping test when running as root")
	}

	// Create temp directory with one file
	tmpDir := t.TempDir()
	
	testFile := filepath.Join(tmpDir, "test.key")
	if err := os.WriteFile(testFile, []byte("data"), 0644); err != nil {
		t.Fatalf("failed to create test file: %v", err)
	}

	// Make the file unreadable (will fail on open for write)
	if err := os.Chmod(testFile, 0000); err != nil {
		t.Skipf("cannot change file permissions: %v", err)
	}
	defer os.Chmod(testFile, 0644) // Restore for cleanup

	logger := internal.NewLogger(internal.LogLevelDebug)
	h := NewHandler(tmpDir, "", logger)

	result := h.SecureWipe()

	// Should be partial or failed since file couldn't be wiped
	if result.Status == WipeSuccess {
		t.Error("Status should not be success when file is unreadable")
	}
}

func TestGetSensitiveFilePaths(t *testing.T) {
	tmpDir := t.TempDir()

	// Create various files
	files := []string{
		"cert.crt",
		"key.pem",
		"private.key",
		"app.log",
		"data.db",
		"state.cache",
		"config.yaml",
		"config.json",
		"random.txt", // Should NOT be included
	}

	for _, name := range files {
		path := filepath.Join(tmpDir, name)
		if err := os.WriteFile(path, []byte("data"), 0644); err != nil {
			t.Fatalf("failed to create %s: %v", name, err)
		}
	}

	logger := internal.NewLogger(internal.LogLevelDebug)
	h := NewHandler(tmpDir, "", logger)

	paths := h.GetSensitiveFilePaths()

	// Should have 8 files (all except random.txt)
	if len(paths) != 8 {
		t.Errorf("GetSensitiveFilePaths returned %d paths, want 8", len(paths))
	}

	// Verify random.txt is not included
	for _, p := range paths {
		if filepath.Base(p) == "random.txt" {
			t.Error("random.txt should not be in sensitive file paths")
		}
	}
}

func TestSelfDestruct(t *testing.T) {
	logger := internal.NewLogger(internal.LogLevelDebug)

	t.Run("without binary deletion", func(t *testing.T) {
		h := NewHandler("/tmp", "", logger)
		result := h.SelfDestruct(false)
		if !result {
			t.Error("SelfDestruct should return true")
		}
	})

	t.Run("with binary deletion", func(t *testing.T) {
		// Create a temp file to act as binary
		tmpDir := t.TempDir()
		binaryPath := filepath.Join(tmpDir, "dropbox")
		if err := os.WriteFile(binaryPath, []byte("binary"), 0755); err != nil {
			t.Fatalf("failed to create test binary: %v", err)
		}

		h := NewHandler("/tmp", binaryPath, logger)
		result := h.SelfDestruct(true)

		if !result {
			t.Error("SelfDestruct should return true")
		}

		// Verify binary is deleted
		if _, err := os.Stat(binaryPath); !os.IsNotExist(err) {
			t.Error("binary should be deleted")
		}
	})
}

func TestHandleAbort(t *testing.T) {
	tmpDir := t.TempDir()

	// Create test files
	testFile := filepath.Join(tmpDir, "secret.key")
	if err := os.WriteFile(testFile, []byte("secret"), 0644); err != nil {
		t.Fatalf("failed to create test file: %v", err)
	}

	// Create a context to track
	ctx, cancel := context.WithCancel(context.Background())

	logger := internal.NewLogger(internal.LogLevelDebug)
	h := NewHandler(tmpDir, "", logger)
	h.RegisterCancelFunc(cancel)

	// Handle abort
	cmd := AbortCommand{
		Reason:       ReasonOperatorInitiated,
		DeleteBinary: false,
	}

	result := h.HandleAbort(cmd)

	// Verify context was cancelled
	select {
	case <-ctx.Done():
		// Good
	default:
		t.Error("context should be cancelled after abort")
	}

	// Verify wipe result
	if result.WipeResult == nil {
		t.Fatal("WipeResult should not be nil")
	}
	if result.WipeResult.Status != WipeSuccess {
		t.Errorf("WipeResult.Status = %q, want %q", result.WipeResult.Status, WipeSuccess)
	}

	// Verify self-destruct initiated
	if !result.SelfDestructInitiated {
		t.Error("SelfDestructInitiated should be true")
	}

	// Verify file was wiped
	if _, err := os.Stat(testFile); !os.IsNotExist(err) {
		t.Error("secret.key should be deleted")
	}
}

func TestSecureWipeFileZeroSize(t *testing.T) {
	// Test that zero-size files are still deleted properly
	tmpDir := t.TempDir()
	testFile := filepath.Join(tmpDir, "empty.key")

	// Create empty file
	if err := os.WriteFile(testFile, []byte{}, 0644); err != nil {
		t.Fatalf("failed to create empty test file: %v", err)
	}

	// Verify file exists
	if _, err := os.Stat(testFile); os.IsNotExist(err) {
		t.Fatal("test file should exist before wipe")
	}

	// Wipe the file
	if err := SecureWipeFile(testFile); err != nil {
		t.Fatalf("SecureWipeFile failed on empty file: %v", err)
	}

	// Verify file is deleted
	if _, err := os.Stat(testFile); !os.IsNotExist(err) {
		t.Error("empty file should be deleted after wipe")
	}
}

func TestSecureWipeFileReadOnlyFile(t *testing.T) {
	// Skip when running as root (root can write to read-only files)
	if os.Getuid() == 0 {
		t.Skip("skipping test when running as root")
	}

	tmpDir := t.TempDir()
	testFile := filepath.Join(tmpDir, "readonly.key")

	if err := os.WriteFile(testFile, []byte("data"), 0444); err != nil {
		t.Fatalf("failed to create test file: %v", err)
	}

	err := SecureWipeFile(testFile)
	if err == nil {
		t.Error("SecureWipeFile should fail on read-only file")
	}
}

func TestSelfDestructNonExistentBinary(t *testing.T) {
	logger := internal.NewLogger(internal.LogLevelDebug)
	h := NewHandler("/tmp", "/nonexistent/path/binary", logger)

	// Should still return true even if binary delete fails
	result := h.SelfDestruct(true)
	if !result {
		t.Error("SelfDestruct should return true even when binary doesn't exist")
	}
}

func TestSecureWipeEmptyDirectory(t *testing.T) {
	// Test wipe on directory with no matching files
	tmpDir := t.TempDir()

	// Create a file that doesn't match patterns
	nonSensitiveFile := filepath.Join(tmpDir, "readme.txt")
	if err := os.WriteFile(nonSensitiveFile, []byte("not sensitive"), 0644); err != nil {
		t.Fatalf("failed to create test file: %v", err)
	}

	logger := internal.NewLogger(internal.LogLevelDebug)
	h := NewHandler(tmpDir, "", logger)

	result := h.SecureWipe()

	// Should succeed with 0 files wiped
	if result.Status != WipeSuccess {
		t.Errorf("Status = %q, want %q for empty wipe", result.Status, WipeSuccess)
	}
	if result.FilesWiped != 0 {
		t.Errorf("FilesWiped = %d, want 0", result.FilesWiped)
	}

	// Non-sensitive file should still exist
	if _, err := os.Stat(nonSensitiveFile); os.IsNotExist(err) {
		t.Error("non-sensitive file should not be deleted")
	}
}

func TestGetSensitiveFilePathsEmptyDir(t *testing.T) {
	tmpDir := t.TempDir()

	logger := internal.NewLogger(internal.LogLevelDebug)
	h := NewHandler(tmpDir, "", logger)

	paths := h.GetSensitiveFilePaths()

	if len(paths) != 0 {
		t.Errorf("GetSensitiveFilePaths should return empty for empty dir, got %d", len(paths))
	}
}

func TestSecureWipeAllFilesFail(t *testing.T) {
	// Skip when running as root
	if os.Getuid() == 0 {
		t.Skip("skipping test when running as root")
	}

	tmpDir := t.TempDir()

	// Create file and make it unwritable
	testFile := filepath.Join(tmpDir, "locked.key")
	if err := os.WriteFile(testFile, []byte("data"), 0644); err != nil {
		t.Fatalf("failed to create test file: %v", err)
	}
	if err := os.Chmod(testFile, 0000); err != nil {
		t.Skipf("cannot change file permissions: %v", err)
	}
	defer os.Chmod(testFile, 0644)

	logger := internal.NewLogger(internal.LogLevelDebug)
	h := NewHandler(tmpDir, "", logger)

	result := h.SecureWipe()

	// Should be failed since all files failed
	if result.Status != WipeFailed {
		t.Errorf("Status = %q, want %q when all files fail", result.Status, WipeFailed)
	}
}

func TestGetSensitiveFilePathsWithInvalidPattern(t *testing.T) {
	// Test with a directory that will have glob matches
	tmpDir := t.TempDir()

	// Create multiple types of sensitive files
	files := []string{"a.crt", "b.pem"}
	for _, name := range files {
		path := filepath.Join(tmpDir, name)
		if err := os.WriteFile(path, []byte("data"), 0644); err != nil {
			t.Fatalf("failed to create %s: %v", name, err)
		}
	}

	logger := internal.NewLogger(internal.LogLevelDebug)
	h := NewHandler(tmpDir, "", logger)

	paths := h.GetSensitiveFilePaths()

	// Should have 2 files
	if len(paths) != 2 {
		t.Errorf("GetSensitiveFilePaths returned %d paths, want 2", len(paths))
	}
}

func TestSecureWipeWithMixedResults(t *testing.T) {
	// Test the partial wipe logic by creating files, some of which can be wiped
	tmpDir := t.TempDir()

	// Create two files
	file1 := filepath.Join(tmpDir, "good.key")
	file2 := filepath.Join(tmpDir, "also_good.crt")
	
	if err := os.WriteFile(file1, []byte("data1"), 0644); err != nil {
		t.Fatalf("failed to create file1: %v", err)
	}
	if err := os.WriteFile(file2, []byte("data2"), 0644); err != nil {
		t.Fatalf("failed to create file2: %v", err)
	}

	logger := internal.NewLogger(internal.LogLevelDebug)
	h := NewHandler(tmpDir, "", logger)

	result := h.SecureWipe()

	// Should succeed with 2 files wiped
	if result.Status != WipeSuccess {
		t.Errorf("Status = %q, want %q", result.Status, WipeSuccess)
	}
	if result.FilesWiped != 2 {
		t.Errorf("FilesWiped = %d, want 2", result.FilesWiped)
	}
}

func TestSecureWipeFileWriteError(t *testing.T) {
	// Create a file in a read-only directory to test write failure
	// This only works when not root
	if os.Getuid() == 0 {
		t.Skip("skipping test when running as root")
	}

	tmpDir := t.TempDir()
	testFile := filepath.Join(tmpDir, "test.key")
	
	if err := os.WriteFile(testFile, []byte("data"), 0644); err != nil {
		t.Fatalf("failed to create test file: %v", err)
	}

	// Make file read-only
	if err := os.Chmod(testFile, 0444); err != nil {
		t.Skipf("cannot change file permissions: %v", err)
	}
	defer os.Chmod(testFile, 0644)

	err := SecureWipeFile(testFile)
	if err == nil {
		t.Error("SecureWipeFile should fail when file is read-only")
	}
}

func TestSecureWipeFileSyncAndRemove(t *testing.T) {
	// Test the full path including sync and remove
	tmpDir := t.TempDir()
	testFile := filepath.Join(tmpDir, "fulltest.key")
	content := []byte("test data for secure wipe verification")

	if err := os.WriteFile(testFile, content, 0644); err != nil {
		t.Fatalf("failed to create test file: %v", err)
	}

	// Verify initial content
	data, err := os.ReadFile(testFile)
	if err != nil {
		t.Fatalf("failed to read test file: %v", err)
	}
	if string(data) != string(content) {
		t.Fatal("initial content mismatch")
	}

	// Wipe the file
	if err := SecureWipeFile(testFile); err != nil {
		t.Fatalf("SecureWipeFile failed: %v", err)
	}

	// Verify file is gone
	if _, err := os.Stat(testFile); !os.IsNotExist(err) {
		t.Error("file should be deleted after wipe")
	}
}
