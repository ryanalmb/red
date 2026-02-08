package wifi

import (
	"context"
	"errors"
	"testing"
	"time"
)

func TestNewRealExecutor(t *testing.T) {
	executor := NewRealExecutor()

	if executor == nil {
		t.Fatal("NewRealExecutor returned nil")
	}
	if executor.Timeout != 30*time.Second {
		t.Errorf("Timeout = %v, want %v", executor.Timeout, 30*time.Second)
	}
}

func TestRealExecutor_Run(t *testing.T) {
	executor := NewRealExecutor()
	executor.Timeout = 5 * time.Second

	// Test with a simple command that should exist on any system
	output, err := executor.Run("echo", "hello")
	if err != nil {
		t.Fatalf("Run(echo hello) error = %v", err)
	}

	expected := "hello\n"
	if string(output) != expected {
		t.Errorf("Run(echo hello) = %q, want %q", string(output), expected)
	}
}

func TestRealExecutor_RunContext(t *testing.T) {
	executor := NewRealExecutor()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	output, err := executor.RunContext(ctx, "echo", "test")
	if err != nil {
		t.Fatalf("RunContext error = %v", err)
	}

	expected := "test\n"
	if string(output) != expected {
		t.Errorf("RunContext = %q, want %q", string(output), expected)
	}
}

func TestRealExecutor_RunContext_Timeout(t *testing.T) {
	executor := NewRealExecutor()

	// Create a context that times out immediately
	ctx, cancel := context.WithTimeout(context.Background(), 1*time.Millisecond)
	defer cancel()

	// Sleep command should be killed by context timeout
	_, err := executor.RunContext(ctx, "sleep", "10")
	if err == nil {
		t.Error("RunContext with expired context should return error")
	}
}

func TestNewMockExecutor(t *testing.T) {
	executor := NewMockExecutor()

	if executor == nil {
		t.Fatal("NewMockExecutor returned nil")
	}
	if executor.responses == nil {
		t.Error("responses map should be initialized")
	}
	if executor.Calls == nil {
		t.Error("Calls slice should be initialized")
	}
}

func TestMockExecutor_SetResponse(t *testing.T) {
	executor := NewMockExecutor()

	expectedOutput := []byte("mock output")
	expectedErr := errors.New("mock error")

	executor.SetResponse("testcmd", expectedOutput, expectedErr)

	output, err := executor.Run("testcmd", "arg1", "arg2")

	if string(output) != string(expectedOutput) {
		t.Errorf("output = %q, want %q", string(output), string(expectedOutput))
	}
	if err != expectedErr {
		t.Errorf("error = %v, want %v", err, expectedErr)
	}
}

func TestMockExecutor_SetResponseWithArgs(t *testing.T) {
	executor := NewMockExecutor()

	expectedOutput := []byte("specific output")
	executor.SetResponseWithArgs("cmd arg1 arg2", expectedOutput, nil)

	// With matching args
	output, err := executor.Run("cmd", "arg1", "arg2")
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}
	if string(output) != string(expectedOutput) {
		t.Errorf("output = %q, want %q", string(output), string(expectedOutput))
	}

	// With different args (should return default)
	output2, _ := executor.Run("cmd", "other")
	if string(output2) == string(expectedOutput) {
		t.Error("different args should not match specific response")
	}
}

func TestMockExecutor_RecordsCalls(t *testing.T) {
	executor := NewMockExecutor()

	executor.Run("cmd1", "a", "b")
	executor.Run("cmd2", "c")
	executor.RunContext(context.Background(), "cmd3")

	if len(executor.Calls) != 3 {
		t.Fatalf("len(Calls) = %d, want 3", len(executor.Calls))
	}

	tests := []struct {
		idx      int
		wantName string
		wantArgs []string
	}{
		{0, "cmd1", []string{"a", "b"}},
		{1, "cmd2", []string{"c"}},
		{2, "cmd3", nil},
	}

	for _, tt := range tests {
		call := executor.Calls[tt.idx]
		if call.Name != tt.wantName {
			t.Errorf("Call[%d].Name = %q, want %q", tt.idx, call.Name, tt.wantName)
		}
		if len(call.Args) != len(tt.wantArgs) {
			t.Errorf("Call[%d].Args len = %d, want %d", tt.idx, len(call.Args), len(tt.wantArgs))
		}
	}
}

func TestMockExecutor_DefaultResponse(t *testing.T) {
	executor := NewMockExecutor()
	executor.DefaultOutput = []byte("default")
	executor.DefaultError = errors.New("default error")

	output, err := executor.Run("unknown")

	if string(output) != "default" {
		t.Errorf("output = %q, want %q", string(output), "default")
	}
	if err.Error() != "default error" {
		t.Errorf("error = %v, want %v", err, "default error")
	}
}

func TestMockExecutor_Start(t *testing.T) {
	executor := NewMockExecutor()
	executor.SetResponse("longcmd", []byte("done"), nil)

	proc, err := executor.Start("longcmd", "arg")
	if err != nil {
		t.Fatalf("Start error = %v", err)
	}

	if proc.Pid() != 12345 {
		t.Errorf("Pid() = %d, want 12345", proc.Pid())
	}

	output, err := proc.Wait()
	if err != nil {
		t.Errorf("Wait error = %v", err)
	}
	if string(output) != "done" {
		t.Errorf("Wait output = %q, want %q", string(output), "done")
	}
}

func TestMockExecutor_Start_Error(t *testing.T) {
	executor := NewMockExecutor()
	expectedErr := errors.New("start failed")
	executor.SetResponse("failcmd", nil, expectedErr)

	_, err := executor.Start("failcmd")
	if err != expectedErr {
		t.Errorf("Start error = %v, want %v", err, expectedErr)
	}
}

func TestMockProcess_Kill(t *testing.T) {
	executor := NewMockExecutor()
	executor.SetResponse("cmd", []byte("output"), nil)

	proc, _ := executor.Start("cmd")
	
	if err := proc.Kill(); err != nil {
		t.Errorf("Kill error = %v", err)
	}

	// After kill, Wait should return nil
	output, _ := proc.Wait()
	if output != nil {
		t.Errorf("Wait after Kill should return nil output, got %q", string(output))
	}
}
