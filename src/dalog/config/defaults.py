"""
Default configuration for DaLog.
"""

from .models import (
    AppConfig,
    DaLogConfig,
    DisplayConfig,
    ExclusionConfig,
    HtmlConfig,
    KeyBindings,
    StylePattern,
    StylingConfig,
)


def get_default_config() -> DaLogConfig:
    """Get default configuration."""
    return DaLogConfig(
        app=AppConfig(
            default_tail_lines=1000,
            live_reload=True,
            case_sensitive_search=False,
            vim_mode=True,
        ),
        keybindings=KeyBindings(
            search="/",
            reload="r",
            toggle_live_reload="L",
            toggle_wrap="w",
            quit="q",
            show_exclusions="e",
            scroll_down="j",
            scroll_up="k",
            scroll_left="h",
            scroll_right="l",
            scroll_home="g",
            scroll_end="G",
        ),
        display=DisplayConfig(
            show_line_numbers=True,
            wrap_lines=False,
            max_line_length=1000,
            visual_mode_bg="#504945",
        ),
        styling=StylingConfig(
            patterns={
                "error": StylePattern(
                    pattern=r"\b(ERROR|FAIL|FAILED|FAILURE|EXCEPTION)\b",
                    color="#ebdbb2",
                    background="#cc241d",
                    bold=True,
                ),
                "warning": StylePattern(
                    pattern=r"\b(WARN|WARNING)\b",
                    color="#282828",
                    background="#d79921",
                    bold=True,
                ),
                "notice": StylePattern(
                    pattern=r"\b(NOTICE|PHP Notice)\b",
                    color="#282828",
                    background="#928374",
                    bold=True,
                ),
                "info": StylePattern(
                    pattern=r"\b(INFO|INFORMATION)\b",
                    color="#ebdbb2",
                    background="#458588",
                    bold=True,
                ),
                "debug": StylePattern(
                    pattern=r"\b(DEBUG|TRACE)\b",
                    color="#ebdbb2",
                    background="#665c54",
                    bold=True,
                ),
                "success": StylePattern(
                    pattern=r"\b(SUCCESS|OK|PASSED|COMPLETE)\b",
                    color="#ebdbb2",
                    background="#98971a",
                    bold=True,
                ),
                "function_name": StylePattern(
                    pattern=r"\b(Function|function|func|Func|method|Method|def|Def)\s+(\w+)",
                    color="#fabd2f",
                    bold=True,
                ),
                "class_name": StylePattern(
                    pattern=r"\b(Class|class|Type|type|interface|Interface)\s+(\w+)",
                    color="#b8bb26",
                    bold=True,
                ),
                "file_path": StylePattern(
                    pattern=r"\b(?:in|at|from|file|File)\s+([\/\w\-\.]+\.\w+)",
                    color="#83a598",
                    underline=True,
                ),
                "line_number": StylePattern(
                    pattern=r"\b(?:line|Line|L)\s+(\d+)", color="#d3869b"
                ),
                "variable_name": StylePattern(
                    pattern=r"\b(?:variable|Variable|var|Var|param|Param|argument|Argument)\s+(\w+)",
                    color="#83a598",
                ),
                "module_name": StylePattern(
                    pattern=r"\b(?:module|Module|package|Package|namespace|Namespace)\s+(\w+)",
                    color="#8ec07c",
                ),
                "error_code": StylePattern(
                    pattern=r"\b(?:error|Error|code|Code)\s+(E\d+|\w+_ERROR|\w+_ERR)",
                    color="#fb4934",
                    bold=True,
                ),
            },
            timestamps={
                "iso_datetime": StylePattern(
                    pattern=r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:,\d{3})?",
                    color="#282828",
                    background="#a89984",
                    bold=True,
                ),
                "standard_date": StylePattern(
                    pattern=r"\d{4}-\d{2}-\d{2}",
                    color="#282828",
                    background="#928374",
                ),
                "time_only": StylePattern(
                    pattern=r"\b\d{2}:\d{2}:\d{2}(?:[,\.]\d{3})?\b",
                    color="#282828",
                    background="#928374",
                ),
                "log_timestamp": StylePattern(
                    pattern=r"^\[[\d\s:-]+\]", color="#282828", background="#928374"
                ),
                "iso_datetime_dot": StylePattern(
                    pattern=r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}\.\d{3}",
                    color="#282828",
                    background="#a89984",
                    bold=True,
                ),
                "bracketed_datetime": StylePattern(
                    pattern=r"\[\d{1,2}-[A-Za-z]{3}-\d{4} \d{2}:\d{2}:\d{2} [A-Z]{3,4}\]",
                    color="#282828",
                    background="#a89984",
                    bold=True,
                ),
            },
            custom={
                "ip_address": StylePattern(
                    pattern=r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b", color="#d3869b"
                ),
                "url": StylePattern(
                    pattern=r"https?://[^\s]+", color="#458588", underline=True
                ),
                "email": StylePattern(
                    pattern=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
                    color="#8ec07c",
                ),
                "uuid": StylePattern(
                    pattern=r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
                    color="#d79921",
                ),
                "json_object": StylePattern(
                    pattern=r"\{[^{}]*\}",
                    color="#fe8019",
                    bold=True,
                ),
                "function_name": StylePattern(
                    pattern=r"\b(Function|function|func|Func|method|Method|def|Def)\s+(\w+)",
                    color="#fabd2f",
                    bold=True,
                ),
                "class_name": StylePattern(
                    pattern=r"\b(Class|class|Type|type|interface|Interface)\s+(\w+)",
                    color="#b8bb26",
                    bold=True,
                ),
                "file_path": StylePattern(
                    pattern=r"\b(?:in|at|from|file|File)\s+([\/\w\-\.]+\.\w+)",
                    color="#83a598",
                    underline=True,
                ),
                "line_number": StylePattern(
                    pattern=r"\b(?:line|Line|L)\s+(\d+)", color="#d3869b"
                ),
                "variable_name": StylePattern(
                    pattern=r"\b(?:variable|Variable|var|Var|param|Param|argument|Argument)\s+(\w+)",
                    color="#83a598",
                ),
                "module_name": StylePattern(
                    pattern=r"\b(?:module|Module|package|Package|namespace|Namespace)\s+(\w+)",
                    color="#8ec07c",
                ),
                "error_code": StylePattern(
                    pattern=r"\b(?:error|Error|code|Code)\s+(E\d+|\w+_ERROR|\w+_ERR)",
                    color="#fb4934",
                    bold=True,
                ),
            },
        ),
        html=HtmlConfig(
            enabled_tags=["b", "i", "em", "strong", "span", "code", "a"],
            strip_unknown_tags=True,
        ),
        exclusions=ExclusionConfig(patterns=[], regex=True, case_sensitive=False),
    )


DEFAULT_CONFIG_TOML = """# DaLog Configuration File

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
visual_mode_bg = "white"

[styling]
# Pattern-based styling rules with regex support
[styling.patterns]
[styling.patterns.error]
pattern = "\\b(ERROR|FAIL|FAILED|FAILURE|EXCEPTION)\\b"
background = "red"
color = "white"
bold = true

[styling.patterns.warning]
pattern = "\\b(WARN|WARNING)\\b"
background = "yellow"
color = "black"
bold = true

[styling.patterns.notice]
pattern = "\\b(NOTICE|PHP Notice)\\b"
background = "white"
color = "black"
bold = true

[styling.patterns.info]
pattern = "\\b(INFO|INFORMATION)\\b"
background = "blue"
color = "white"
bold = true

[styling.patterns.debug]
pattern = "\\b(DEBUG|TRACE)\\b"
background = "bright_black"
color = "white"
bold = true

[styling.patterns.success]
pattern = "\\b(SUCCESS|OK|PASSED|COMPLETE)\\b"
background = "green"
color = "white"
bold = true

# Timestamp and date styling
[styling.timestamps]
[styling.timestamps.iso_datetime]
pattern = "\\d{4}-\\d{2}-\\d{2}[T ]\\d{2}:\\d{2}:\\d{2}(?:,\\d{3})?"
color = "black"
background = "bright_black"
bold = true

[styling.timestamps.standard_date]
pattern = "\\d{4}-\\d{2}-\\d{2}"
color = "black"
background = "bright_black"

[styling.timestamps.time_only]
pattern = "\\b\\d{2}:\\d{2}:\\d{2}(?:[,\\.]\\d{3})?\\b"
color = "black"
background = "bright_black"

[styling.timestamps.log_timestamp]
pattern = "^\\[[\\d\\s:-]+\\]"
color = "black"
background = "bright_black"

[styling.timestamps.iso_datetime_dot]
pattern = "\\d{4}-\\d{2}-\\d{2}[T ]\\d{2}:\\d{2}:\\d{2}\\.\\d{3}"
color = "black"
background = "bright_black"
bold = true

[styling.timestamps.bracketed_datetime]
pattern = "\\[\\d{1,2}-[A-Za-z]{3}-\\d{4} \\d{2}:\\d{2}:\\d{2} [A-Z]{3,4}\\]"
color = "black"
background = "bright_black"
bold = true

# Custom regex patterns
[styling.custom]
[styling.custom.ip_address]
pattern = "\\b(?:[0-9]{1,3}\\.){3}[0-9]{1,3}\\b"
color = "magenta"

[styling.custom.url]
pattern = "https?://[^\\s]+"
color = "blue"
underline = true

[styling.custom.email]
pattern = "\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b"
color = "cyan"

[styling.custom.uuid]
pattern = "\\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\\b"
color = "yellow"

[styling.custom.function_name]
pattern = "\\b(Function|function|func|Func|method|Method|def|Def)\\s+(\\w+)"
color = "bright_yellow"
bold = true

[styling.custom.class_name]
pattern = "\\b(Class|class|Type|type|interface|Interface)\\s+(\\w+)"
color = "bright_green"
bold = true

[styling.custom.file_path]
pattern = "\\b(?:in|at|from|file|File)\\s+([/\\w\\-\\.]+\\.\\w+)"
color = "cyan"
underline = true

[styling.custom.line_number]
pattern = "\\b(?:line|Line|L)\\s+(\\d+)"
color = "bright_magenta"

[styling.custom.variable_name]
pattern = "\\b(?:variable|Variable|var|Var|param|Param|argument|Argument)\\s+(\\w+)"
color = "bright_blue"

[styling.custom.module_name]
pattern = "\\b(?:module|Module|package|Package|namespace|Namespace)\\s+(\\w+)"
color = "bright_cyan"

[styling.custom.error_code]
pattern = "\\b(?:error|Error|code|Code)\\s+(E\\d+|\\w+_ERROR|\\w+_ERR)"
color = "bright_red"
bold = true

[html]
# HTML elements to render
enabled_tags = ["b", "i", "em", "strong", "span", "code", "a"]
strip_unknown_tags = true

[exclusions]
# Default exclusion patterns (also support regex)
patterns = []
regex = true
case_sensitive = false
"""
