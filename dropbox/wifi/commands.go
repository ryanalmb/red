// Package wifi provides wrappers for WiFi security tools.
package wifi

// CommandType represents the type of WiFi command to execute.
type CommandType string

const (
	// CommandScan initiates a network scan.
	CommandScan CommandType = "scan"

	// CommandCapture initiates handshake capture.
	CommandCapture CommandType = "capture"

	// CommandDeauth initiates deauthentication attack.
	CommandDeauth CommandType = "deauth"

	// CommandCrack initiates password cracking.
	CommandCrack CommandType = "crack"

	// CommandMonitor enables/disables monitor mode.
	CommandMonitor CommandType = "monitor"
)

// Command represents a WiFi toolkit command to be executed.
type Command struct {
	// Type is the command type.
	Type CommandType

	// Target is the target BSSID or ESSID.
	Target string

	// Options contains command-specific options.
	Options map[string]interface{}
}

// NewCommand creates a new Command with the specified type and target.
func NewCommand(cmdType CommandType, target string) *Command {
	return &Command{
		Type:    cmdType,
		Target:  target,
		Options: make(map[string]interface{}),
	}
}

// SetOption sets a command option.
func (c *Command) SetOption(key string, value interface{}) *Command {
	c.Options[key] = value
	return c
}

// Result represents the result of a WiFi command execution.
type Result struct {
	// Success indicates whether the command succeeded.
	Success bool

	// Output contains the command output.
	Output string

	// Error contains any error message.
	Error string

	// Data contains structured result data.
	Data interface{}
}

// NewResult creates a new Result.
func NewResult(success bool, output string) *Result {
	return &Result{
		Success: success,
		Output:  output,
	}
}

// WithError adds an error message to the result.
func (r *Result) WithError(err string) *Result {
	r.Error = err
	r.Success = false
	return r
}

// WithData adds structured data to the result.
func (r *Result) WithData(data interface{}) *Result {
	r.Data = data
	return r
}
