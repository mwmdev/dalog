# `dalog` - Your friendly terminal logs viewer

![Version](https://img.shields.io/badge/version-0.1.1-blue)
![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

`dalog` is a terminal-based log viewing application built with Python and Textual. It provides advanced features for viewing, searching, and analyzing log files with a modern, keyboard-driven interface optimized for developer workflows.

![dalog](./public/dalog.png)

## Features

- **Live Search**: Real-time filtering 
- **SSH Support**: Read remote logs via SSH 
- **Exclusion System**: Filter out unwanted log entries with persistent patterns and regex
- **Smart Styling**: Pattern-based syntax highlighting with regex support
- **Live Reload**: Automatically update when log files change (like `tail -f`) - supports both local and SSH files
- **Visual Mode**: Visual line selection with clipboard support
- **HTML Rendering**: Render HTML tags in logs (configurable tags)
- **Vim Keybindings**: Full vim-style navigation with customizable keybindings
- **Configurable**: Extensive configuration options via TOML files
- **CLI Exclusions**: Filter logs directly from command line with `--exclude` parameter
- **Theme Support**: Choose from built-in Textual themes via CLI

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
# View a single log file
dalog application.log

# View a remote log file via SSH
dalog user@server:/var/log/application.log

# Start with search pre-filled
dalog --search ERROR application.log

# Search in remote logs
dalog --search ERROR user@server:/var/log/app.log

# Exclude unwanted log levels
dalog --exclude "WARNING" application.log

# Load only last 1000 lines (works with SSH too!)
dalog --tail 1000 user@server:/var/log/large-application.log

# Use custom configuration
dalog --config ~/.config/dalog/custom.toml app.log

# Use a specific Textual theme
dalog --theme gruvbox error.log

# Combine multiple options with SSH
dalog --search ERROR --exclude DEBUG --tail 500 user@host:/var/log/app.log
```

### CLI Arguments

#### Required Arguments

- **`log_file`** - The path to the log file you want to view (local or SSH)
  - Local files: Must be an existing, readable file
  - SSH format: `user@host:/path/to/log` or `ssh://user@host:port/path/to/log`
  - Examples: 
    - `dalog application.log`
    - `dalog /var/log/app.log`
    - `dalog user@server:/var/log/nginx/access.log`
    - `dalog admin@192.168.1.10:2222:/logs/app.log`

#### Optional Arguments

- **`--config` / `-c`** - Specify a custom configuration file
  - Type: Path to existing TOML configuration file
  - Example: `dalog --config ~/.config/dalog/custom.toml app.log`
  - If not specified, dalog searches for config files in the standard locations

- **`--search` / `-s`** - Start dalog with a search term already applied
  - Type: String (search term or regex pattern)
  - Example: `dalog --search "ERROR" app.log`
  - Example: `dalog -s "user_id=\\d+" app.log` (regex pattern)

- **`--tail` / `-t`** - Load only the last N lines from the file
  - Type: Integer (number of lines)
  - Useful for large log files to improve startup performance
  - Example: `dalog --tail 1000 large-app.log`
  - Example: `dalog -t 500 app.log`

- **`--theme`** - Set the visual theme for the application
  - Type: String (theme name)
  - Available themes include: `textual-dark`, `textual-light`, `nord`, `gruvbox`, `catppuccin-mocha`, `dracula`, `tokyo-night`, `monokai`, `flexoki`, `catppuccin-latte`, `solarized-light`
  - Example: `dalog --theme gruvbox app.log`
  - Example: `dalog --theme nord error.log`

- **`--exclude` / `-e`** - Exclude lines matching the specified pattern
  - Type: String (pattern or regex)
  - Can be used multiple times to exclude multiple patterns
  - Patterns are **case-sensitive** and support **regex**
  - Applied in addition to config file exclusions
  - Example: `dalog --exclude "DEBUG" app.log`
  - Example: `dalog -e "WARNING" -e "INFO" app.log`
  - Example: `dalog --exclude "ERROR.*timeout" app.log` (regex)

- **`--version` / `-V`** - Display the version number and exit
  - Example: `dalog --version`
  - Example: `dalog -V`

### Default Keybindings

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

DaLog supports vi-style visual line selection:

1. Press `V` (or enter a line number and press `V`) to enter visual line mode
2. Use `j`/`k` to navigate to the desired starting line (cursor shown with underline)
3. Press `v` to start selection from the current cursor position
4. Use `j`/`k` to extend the selection up/down
5. Press `y` to yank (copy) selected lines to clipboard
6. Press `ESC` to exit visual mode without copying

## SSH Support

DaLog can read log files from remote servers via SSH. This is particularly useful for:
- Monitoring production logs without logging into servers
- Viewing logs from multiple servers in separate terminal windows
- Applying your local dalog configuration to remote logs

### SSH URL Format

```
user@host:/path/to/log
user@host:port:/path/to/log
ssh://user@host:port/path/to/log
```

### SSH Authentication

DaLog uses your system's SSH configuration:
- SSH keys from `~/.ssh/`
- SSH agent for key management
- SSH config from `~/.ssh/config`

### Live Reload for SSH

Live reload works with SSH files! DaLog will periodically check for changes and automatically update the display when the remote file is modified.

### Examples

```bash
# View nginx access logs on web server
dalog webadmin@webserver:/var/log/nginx/access.log

# Monitor application errors with filtering
dalog --search ERROR --exclude DEBUG deploy@app-server:/home/app/logs/production.log

# Tail last 500 lines from remote syslog
dalog --tail 500 root@192.168.1.1:/var/log/syslog

# Use custom port
dalog admin@server:2222:/var/log/custom.log
```

## Configuration

DaLog looks for configuration files in the following order:

1. Command-line specified: `--config path/to/config.toml`
2. `$XDG_CONFIG_HOME/dalog/config.toml`
3. `~/.config/dalog/config.toml`
4. `~/.dalog.toml`
5. `./config.toml` (current directory)

### Example Configuration

```toml
[app]
default_tail_lines = 1000
live_reload = true
case_sensitive_search = false
vim_mode = true

[keybindings]
search = "/"
reload = "r"
toggle_live_reload = "L"
toggle_wrap = "w"
quit = "q"
show_exclusions = "e"
scroll_down = "j"
scroll_up = "k"
scroll_left = "h"
scroll_right = "l"
scroll_home = "g"
scroll_end = "G"

[display]
show_line_numbers = true
wrap_lines = false
max_line_length = 1000
visual_mode_bg = "white"  # Background color for visual mode selection

[styling.patterns]
error = { pattern = "(?i)error", background = "red", color = "white" }
warning = { pattern = "(?i)warning", background = "yellow", color = "black", bold = true }
info = { pattern = "(?i)info", color = "blue" }

[styling.timestamps]
iso_datetime = { pattern = "\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}", color = "cyan" }

[html]
# Configure which HTML tags to render in logs
enabled_tags = ["b", "i", "em", "strong", "span", "code", "pre"]
strip_unknown_tags = true

[exclusions]
patterns = ["DEBUG:", "TRACE:"]
regex = true
case_sensitive = false
```

## Styling System

DaLog supports powerful regex-based styling patterns:

```toml
[styling.custom]
# Highlight IP addresses
ip_address = { pattern = "\\b(?:[0-9]{1,3}\\.){3}[0-9]{1,3}\\b", color = "magenta" }

# Highlight URLs
url = { pattern = "https?://[\\w\\.-]+", color = "blue", underline = true }

# Highlight email addresses
email = { pattern = "\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b", color = "cyan" }

# Custom application-specific patterns
user_id = { pattern = "user_id=\\d+", color = "green", bold = true }
```

## Development

### Setting up the development environment

```bash
# Clone the repository
git clone https://github.com/mwmdev/dalog.git
cd dalog

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
black src/
mypy src/
pylint src/
```

### Project Structure

```
dalog/
├── src/dalog/          # Main package
│   ├── app.py          # Textual application
│   ├── cli.py          # Click CLI interface
│   ├── config/         # Configuration management
│   ├── core/           # Core functionality
│   ├── widgets/        # Custom Textual widgets
│   └── styles/         # CSS styles
├── tests/              # Test suite
├── docs/               # Documentation
└── pyproject.toml      # Project configuration
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