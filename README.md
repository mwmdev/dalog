# `dalog` - Your friendly terminal logs viewer

![Version](https://img.shields.io/badge/version-0.2.2-blue)
![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Coverage](https://img.shields.io/badge/coverage-82%25-green)

`dalog` is a terminal-based log viewing application built with Python and Textual. It provides advanced features for viewing, searching, and analyzing log files with a modern, keyboard-driven interface optimized for developer workflows.

![](https://raw.githubusercontent.com/mwmdev/dalog/main/public/dalog.png)

## Features

- **Live Search**: Real-time filtering 
- **SSH Support**: Read remote logs via SSH 
- **Exclusion System**: Filter out unwanted log entries with persistent patterns and regex
- **Smart Styling**: Pattern-based syntax highlighting with regex support
- **Live Reload**: Automatically update when log files change (like `tail -f`) - supports both local and SSH files
- **Visual Mode**: Visual line selection with clipboard support
- **HTML Rendering**: Configurable rendering of HTML tags in logs 
- **Customizable Keybindings**: Fully customizable keybindings
- **Theme Support**: Choose from built-in Textual themes

## Installation

### Via pip (recommended)

```bash
pip install dalog
```

### Development Installation

```bash
# Clone the repository
git clone https://github.com/mwmdev/dalog.git
cd dalog

# Install in development mode
pip install -e .

# Or with development dependencies
pip install -e ".[dev]"
```

## Quick Start

### Basic Usage

```bash
# View a log file
dalog /path/to/logfile.log

# View a remote log file via SSH
dalog user@server:/path/to/logfile.log

# Start with search pre-filled
dalog --search "ERROR" /path/to/logfile.log

# Search in remote logs
dalog user@server:/path/to/logfile.log --search "Exception"

# Exclude unwanted log levels
dalog /path/to/logfile.log --exclude "WARNING"

# Load only last 100 lines 
dalog user@server:/path/to/large-logfile.log --tail 100

# Use custom configuration
dalog /path/to/logfile.log --config ~/.config/dalog/custom.toml

# Use a specific Textual theme
dalog /path/to/logfile.log --theme gruvbox

# Combine multiple options with SSH
dalog user@host:/path/to/logfile.log --search "123.456.789.012" --tail 100 
```

### CLI Arguments

#### Required Arguments

- **`log_file`** - The path to the log file you want to view (local or SSH)
  - Local files: Must be an existing, readable file
  - SSH format: `user@host:/path/to/logfile` or `ssh://user@host:port/path/to/logfile`
  - Examples: 
    - `dalog application.log`
    - `dalog /var/log/app.log`
    - `dalog user@server:/var/log/nginx/access.log`
    - `dalog admin@192.168.1.10:2222:/logs/app.log`

#### Optional Arguments

- **`--config` / `-c`** - Specify a custom configuration file
  - Type: Path to existing TOML configuration file
  - Example: `dalog app.log --config ~/.config/dalog/custom.toml`
  - If not specified, dalog searches for config files in the standard locations

- **`--search` / `-s`** - Start dalog with a search term already applied
  - Type: String (search term or regex pattern)
  - Example: `dalog app.log --search "ERROR"`
  - Example: `dalog app.log -s "user_id=\\d+"` (regex pattern)

- **`--tail` / `-t`** - Load only the last N lines from the file
  - Type: Integer (number of lines)
  - Useful for large log files to improve startup performance
  - Example: `dalog large-app.log --tail 1000`
  - Example: `dalog app.log -t 500`

- **`--theme`** - Set the visual theme for the application
  - Type: String (theme name)
  - Available themes include: `textual-dark`, `textual-light`, `nord`, `gruvbox`, `catppuccin-mocha`, `dracula`, `tokyo-night`, `monokai`, `flexoki`, `catppuccin-latte`, `solarized-light`
  - Example: `dalog app.log --theme gruvbox`
  - Example: `dalog app.log --theme nord`

- **`--exclude` / `-e`** - Exclude lines matching the specified pattern
  - Type: String (pattern or regex)
  - Can be used multiple times to exclude multiple patterns
  - Patterns are **case-sensitive** and support **regex**
  - Applied in addition to config file exclusions
  - Example: `dalog app.log --exclude "DEBUG"`
  - Example: `dalog app.log -e "WARNING" -e "INFO"`
  - Example: `dalog app.log --exclude "ERROR.*timeout"` (regex)

- **`--version` / `-V`** - Display the version number and exit
  - Example: `dalog --version`
  - Example: `dalog -V`

### Default Keybindings

Default keybindings are Vim inspired and designed for efficient navigation and interaction. You can customize these in the `config.toml` file.

| Key | Action |
|-----|--------|
| `/` | Open search |
| `ESC` | Close search/cancel/exit visual mode |
| `j`/`k` | Navigate down/up |
| `h`/`l` | Navigate left/right |
| `g`/`G` | Go to top/bottom |
| `Ctrl+u`/`Ctrl+d` | Page up/down |
| `V` | Enter visual line mode (vi-style selection) |
| `v` | Start selection at cursor (in visual mode) |
| `y` | Yank/copy selected lines to clipboard (in visual mode) |
| `r` | Reload file |
| `L` | Toggle live reload |
| `w` | Toggle text wrapping |
| `e` | Manage exclusions |
| `q` | Quit |

#### Visual Mode

1. Press `V` (or enter a line number and press `V`) to enter visual line mode
2. Use `j`/`k` to navigate to the desired starting line (cursor shown with underline)
3. Press `v` to start selection from the current cursor position
4. Use `j`/`k` to extend the selection up/down
5. Press `y` to yank (copy) selected lines to clipboard
6. Press `ESC` to exit visual mode without copying

## Performance Optimization

`dalog` is designed to handle large log files efficiently, but there are several strategies to optimize performance, especially when working with SSH connections or very large files.

### SSH Performance Tips

#### 1. Use Lower Tail Values for Faster Loading

**The most effective performance improvement for SSH logs is using a smaller `--tail` value:**

```bash
# ✅ Fast - loads only last 50 lines (recommended for SSH)
dalog --tail 50 user@server:/var/log/app.log

# ✅ Good - loads last 200 lines  
dalog --tail 200 user@server:/var/log/app.log

# ⚠️  Slow - loads last 1000 lines (default)
dalog --tail 1000 user@server:/var/log/app.log
```

**Why this helps:**
- Reduces initial data transfer over SSH
- Faster parsing and rendering
- Better memory usage
- Quicker startup time

#### 2. Configure SSH Polling for Real-time Updates

Optimize SSH polling intervals in your config for faster live updates:

```toml
[ssh]
# Ultra-fast polling (great for active development/debugging)
poll_interval = 0.1          # Poll every 100ms when active
max_poll_interval = 1.0      # Max 1s when idle

# Balanced performance (recommended for most use cases)
poll_interval = 0.5          # Poll every 500ms when active  
max_poll_interval = 2.0      # Max 2s when idle

# Conservative (for high-latency or limited bandwidth)
poll_interval = 1.0          # Poll every 1s when active
max_poll_interval = 5.0      # Max 5s when idle
```

#### 3. SSH Connection Optimization

```bash
# Use SSH connection multiplexing in ~/.ssh/config
Host *
    ControlMaster auto
    ControlPath ~/tmp/ssh_mux_%h_%p_%r
    ControlPersist 4h

# Use compression for slow connections
Host slow-server
    Compression yes
    CompressionLevel 6
```

#### Configuration Performance Settings

Add these optimizations to your `config.toml`:

```toml
[app]
# Reduce default tail for faster startup
default_tail_lines = 500    # Instead of 1000

[display]  
# Limit line length for better rendering performance
max_line_length = 500       # Instead of 1000
wrap_lines = false          # Wrapping can slow down rendering

[ssh]
# Optimized SSH polling (adjust based on your needs)
poll_interval = 0.5         # Fast polling when active
max_poll_interval = 2.0     # Reasonable max when idle
connection_timeout = 10     # Faster timeout for unreachable hosts
command_timeout = 30        # Faster command timeout

[exclusions]
# Pre-filter noisy entries for better performance
patterns = [
    "DEBUG:",
    "TRACE:", 
    "healthcheck",
    "static.*GET"
]
```

## Configuration

`dalog` looks for configuration files in the following order:

1. Command-line specified: `--config path/to/config.toml`
2. `$XDG_CONFIG_HOME/dalog/config.toml`
3. `~/.config/dalog/config.toml`
4. `~/.dalog.toml`
5. `./config.toml` (current directory)

### Example Configuration

```toml
[app]
default_tail_lines = 500
live_reload = true
case_sensitive_search = false

[keybindings]
# General commands
search = "/"
reload = "r"
toggle_live_reload = "L"
toggle_wrap = "w"
quit = "q"
show_exclusions = "e"
show_help = "?"

# Navigation
scroll_down = "j"
scroll_up = "k"
scroll_left = "h"
scroll_right = "l"
scroll_home = "g"
scroll_end = "G"
scroll_page_up = "ctrl+u"
scroll_page_down = "ctrl+d"

# Visual mode (vi-style)
enter_visual_mode = "V"
start_selection = "v"
yank_lines = "y"

# Footer display configuration
display_in_footer = [
    "search",
    "reload", 
    "toggle_live_reload",
    "show_exclusions",
    "toggle_wrap",
    "quit",
    "show_help"
]

[display]
show_line_numbers = true
wrap_lines = false
max_line_length = 1000
visual_mode_bg = "white"

[html]
enabled_tags = ["b", "i", "em", "strong", "span", "code", "pre"]
strip_unknown_tags = true

[exclusions]
patterns = ["DEBUG:", "TRACE:", "healthcheck"]
regex = false
case_sensitive = false

[ssh]
# SSH connection and security settings
strict_host_key_checking = true
connection_timeout = 30
command_timeout = 60
max_tail_lines = 1000000

# Poll intervals for SSH file watching (optimized for real-time log streaming)
poll_interval = 0.1          # Fast polling interval in seconds (for active monitoring)
max_poll_interval = 2.0      # Maximum interval when backing off during idle periods

# Optional custom known_hosts file
# known_hosts_file = "/path/to/custom/known_hosts"

# Styling patterns for different log levels and content
[styling.patterns]
error = { pattern = "(?i)\\b(error|fail|failed|failure)\\b", background = "red", color = "white", bold = true }
warning = { pattern = "(?i)\\b(warn|warning)\\b", background = "yellow", color = "black", bold = true }
info = { pattern = "(?i)\\b(info|information)\\b", color = "blue" }
debug = { pattern = "(?i)\\b(debug|trace)\\b", color = "dim" }
success = { pattern = "(?i)\\b(success|successful|succeeded|ok|pass|passed)\\b", color = "green", bold = true }

# Timestamp patterns
[styling.timestamps]
iso_datetime = { pattern = "\\d{4}-\\d{2}-\\d{2}[T ]\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{3})?(?:Z|[+-]\\d{2}:\\d{2})?", color = "cyan", bold = true }
standard_date = { pattern = "\\d{4}-\\d{2}-\\d{2}", color = "cyan" }
time_only = { pattern = "\\b\\d{1,2}:\\d{2}:\\d{2}(?:\\.\\d{3})?\\b", color = "green" }
unix_timestamp = { pattern = "\\b1[0-9]{9}\\b", color = "yellow" }

# Custom patterns
[styling.custom]
ip_address = { pattern = "\\b(?:[0-9]{1,3}\\.){3}[0-9]{1,3}\\b", color = "magenta" }
url = { pattern = "https?://[^\\s]+", color = "blue", underline = true }
email = { pattern = "\\b[\\w\\._%+-]+@[\\w\\.-]+\\.[a-zA-Z]{2,}\\b", color = "cyan", underline = true }
uuid = { pattern = "\\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\\b", color = "yellow" }
json_key = { pattern = '"([^"]+)"\\s*:', color = "green" }
mac_address = { pattern = "\\b([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\\b", color = "magenta" }
file_path = { pattern = "(?:[\\w.-]+/)+[\\w.-]+", color = "blue", italic = true }
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [Textual](https://textual.textualize.io/) - an amazing TUI framework
- Inspired by traditional Unix tools like `tail`, `less`, and `grep`
- Thanks to all contributors and users
