// Package wifi provides wrappers for WiFi security tools.
package wifi

import (
	"context"
	"os/exec"
	"time"
)

// CommandExecutor abstracts command execution for testability.
// Real implementation uses os/exec, mock implementation returns canned responses.
type CommandExecutor interface {
	// Run executes a command and returns combined stdout/stderr output.
	Run(name string, args ...string) ([]byte, error)

	// RunContext executes a command with context for timeout/cancellation support.
	RunContext(ctx context.Context, name string, args ...string) ([]byte, error)

	// Start starts a command without waiting for completion.
	// Returns a Process that can be used to wait or kill the command.
	Start(name string, args ...string) (Process, error)
}

// Process represents a running process that can be waited on or killed.
type Process interface {
	// Wait waits for the process to complete and returns the output.
	Wait() ([]byte, error)

	// Kill terminates the process.
	Kill() error

	// Pid returns the process ID.
	Pid() int
}

// RealExecutor implements CommandExecutor using os/exec.
type RealExecutor struct {
	// Timeout is the default timeout for commands (0 means no timeout).
	Timeout time.Duration
}

// NewRealExecutor creates a new RealExecutor with default settings.
func NewRealExecutor() *RealExecutor {
	return &RealExecutor{
		Timeout: 30 * time.Second,
	}
}

// Run executes a command and returns combined stdout/stderr output.
func (r *RealExecutor) Run(name string, args ...string) ([]byte, error) {
	if r.Timeout > 0 {
		ctx, cancel := context.WithTimeout(context.Background(), r.Timeout)
		defer cancel()
		return r.RunContext(ctx, name, args...)
	}
	cmd := exec.Command(name, args...)
	return cmd.CombinedOutput()
}

// RunContext executes a command with context for timeout/cancellation support.
func (r *RealExecutor) RunContext(ctx context.Context, name string, args ...string) ([]byte, error) {
	cmd := exec.CommandContext(ctx, name, args...)
	return cmd.CombinedOutput()
}

// Start starts a command without waiting for completion.
func (r *RealExecutor) Start(name string, args ...string) (Process, error) {
	cmd := exec.Command(name, args...)
	if err := cmd.Start(); err != nil {
		return nil, err
	}
	return &realProcess{cmd: cmd}, nil
}

// realProcess wraps exec.Cmd to implement Process interface.
type realProcess struct {
	cmd *exec.Cmd
}

// Wait waits for the process to complete and returns the output.
func (p *realProcess) Wait() ([]byte, error) {
	err := p.cmd.Wait()
	return nil, err // Output was already consumed if using pipes
}

// Kill terminates the process.
func (p *realProcess) Kill() error {
	if p.cmd.Process != nil {
		return p.cmd.Process.Kill()
	}
	return nil
}

// Pid returns the process ID.
func (p *realProcess) Pid() int {
	if p.cmd.Process != nil {
		return p.cmd.Process.Pid
	}
	return 0
}

// MockExecutor implements CommandExecutor for testing.
type MockExecutor struct {
	// Responses maps "command args..." to (output, error) pairs.
	// Use SetResponse to configure responses.
	responses map[string]mockResponse

	// Calls records all calls made to the executor.
	Calls []MockCall

	// DefaultOutput is returned when no specific response is configured.
	DefaultOutput []byte

	// DefaultError is returned when no specific response is configured.
	DefaultError error
}

// mockResponse holds a canned response for MockExecutor.
type mockResponse struct {
	output []byte
	err    error
}

// MockCall records a call to MockExecutor.
type MockCall struct {
	Name string
	Args []string
}

// NewMockExecutor creates a new MockExecutor.
func NewMockExecutor() *MockExecutor {
	return &MockExecutor{
		responses: make(map[string]mockResponse),
		Calls:     make([]MockCall, 0),
	}
}

// SetResponse configures a canned response for a specific command.
// The key is the command name; args are matched separately.
func (m *MockExecutor) SetResponse(name string, output []byte, err error) {
	m.responses[name] = mockResponse{output: output, err: err}
}

// SetResponseWithArgs configures a canned response for a specific command with args.
// The key format is "name arg1 arg2 ...".
func (m *MockExecutor) SetResponseWithArgs(key string, output []byte, err error) {
	m.responses[key] = mockResponse{output: output, err: err}
}

// Run executes a mock command.
func (m *MockExecutor) Run(name string, args ...string) ([]byte, error) {
	m.Calls = append(m.Calls, MockCall{Name: name, Args: args})

	// Try exact match with args first
	key := name
	for _, arg := range args {
		key += " " + arg
	}
	if resp, ok := m.responses[key]; ok {
		return resp.output, resp.err
	}

	// Try command name only
	if resp, ok := m.responses[name]; ok {
		return resp.output, resp.err
	}

	return m.DefaultOutput, m.DefaultError
}

// RunContext executes a mock command with context (context is ignored in mock).
func (m *MockExecutor) RunContext(ctx context.Context, name string, args ...string) ([]byte, error) {
	return m.Run(name, args...)
}

// Start starts a mock command (returns immediately with mock process).
func (m *MockExecutor) Start(name string, args ...string) (Process, error) {
	m.Calls = append(m.Calls, MockCall{Name: name, Args: args})

	// Check for error response
	if resp, ok := m.responses[name]; ok && resp.err != nil {
		return nil, resp.err
	}

	return &mockProcess{
		executor: m,
		name:     name,
		args:     args,
	}, nil
}

// mockProcess implements Process for MockExecutor.
type mockProcess struct {
	executor *MockExecutor
	name     string
	args     []string
	killed   bool
}

// Wait returns the configured response for the command.
func (p *mockProcess) Wait() ([]byte, error) {
	if p.killed {
		return nil, nil
	}
	if resp, ok := p.executor.responses[p.name]; ok {
		return resp.output, resp.err
	}
	return p.executor.DefaultOutput, p.executor.DefaultError
}

// Kill marks the process as killed.
func (p *mockProcess) Kill() error {
	p.killed = true
	return nil
}

// Pid returns a fake PID.
func (p *mockProcess) Pid() int {
	return 12345
}
