#!/usr/bin/env python3
"""
Command-line interface for DaLog.
"""

import sys
from pathlib import Path
from typing import List, Optional, Tuple

import click

from . import __version__
from .app import create_dalog_app


def print_version(ctx, param, value):
    """Print version and exit."""
    if not value or ctx.resilient_parsing:
        return
    click.echo(__version__)
    ctx.exit()


def validate_log_source(ctx, param, value):
    """Validate log source (local file or SSH URL) with security checks."""
    from .core.remote_reader import is_ssh_url
    from .security.path_security import PathSecurityError, validate_log_path

    if is_ssh_url(value):
        # It's an SSH URL, no need to check if file exists locally
        return value

    # It's a local file, perform security validation
    try:
        safe_path = validate_log_path(value)

        # Additional checks for existence and file type
        if not safe_path.exists():
            raise click.BadParameter(f"File not found: {value}")
        if not safe_path.is_file():
            raise click.BadParameter(f"Not a file: {value}")

        return str(safe_path)

    except PathSecurityError as e:
        raise click.BadParameter(f"Security error: {e}")
    except Exception as e:
        raise click.BadParameter(f"Invalid file path: {e}")


def validate_config_path(ctx, param, value):
    """Validate configuration file path for security."""
    if not value:
        return value

    from .security.path_security import PathSecurityError, validate_config_path

    try:
        safe_path = validate_config_path(value)

        # Ensure it exists and is readable
        if not safe_path.exists():
            raise click.BadParameter(f"Configuration file not found: {value}")
        if not safe_path.is_file():
            raise click.BadParameter(f"Configuration path is not a file: {value}")

        return str(safe_path)

    except PathSecurityError as e:
        raise click.BadParameter(f"Configuration security error: {e}")
    except Exception as e:
        raise click.BadParameter(f"Invalid configuration path: {e}")


def validate_exclude_pattern(ctx, param, value):
    """Validate exclusion patterns for security."""
    if not value:
        return value

    from .security.regex_security import validate_pattern_security

    validated_patterns = []
    for pattern in value:
        is_safe, error_msg = validate_pattern_security(pattern)
        if not is_safe:
            raise click.BadParameter(
                f"Unsafe exclusion pattern '{pattern}': {error_msg}"
            )
        validated_patterns.append(pattern)

    return tuple(validated_patterns)


@click.command()
@click.argument(
    "log_file",
    required=True,
    callback=validate_log_source,
)
@click.option(
    "--config",
    "-c",
    type=str,
    callback=validate_config_path,
    help="Path to configuration file",
)
@click.option(
    "--search",
    "-s",
    type=str,
    help="Initial search term to filter logs",
)
@click.option(
    "--tail",
    "-t",
    type=int,
    help="Load only last N lines of the file",
)
@click.option(
    "--theme",
    type=str,
    help="Set the Textual theme (e.g., nord, gruvbox, tokyo-night, textual-dark)",
)
@click.option(
    "--exclude",
    "-e",
    type=str,
    multiple=True,
    callback=validate_exclude_pattern,
    help="Exclude lines matching pattern (can be used multiple times). Supports regex patterns and is case-sensitive.",
)
@click.option(
    "--version",
    "-V",
    is_flag=True,
    callback=print_version,
    expose_value=False,
    is_eager=True,
    help="Show the version and exit.",
)
def main(
    log_file: str,
    config: Optional[str],
    search: Optional[str],
    tail: Optional[int],
    theme: Optional[str],
    exclude: Tuple[str, ...],
) -> None:
    """
    dalog - Your friendly terminal logs viewer

    View and search a log file with a modern terminal interface.
    Supports both local files and remote files via SSH.

    Examples:

        dalog app.log

        dalog user@host:/var/log/app.log

        dalog --search ERROR app.log

        dalog --tail 1000 user@host:/var/log/large-app.log

        dalog --config ~/.config/dalog/custom.toml app.log

        dalog --exclude "DEBUG" --exclude "INFO" app.log

        dalog --exclude "ERROR.*timeout" user@host:/var/log/app.log
    """
    # Use log_file directly since it's already validated
    log_file_path = log_file

    # Convert exclude tuple to list
    exclude_patterns = list(exclude) if exclude else []

    # Create and run the application
    try:
        # Create the app class with dynamic bindings
        DaLogApp = create_dalog_app(config)

        # Create app instance
        app = DaLogApp(
            log_file=log_file_path,
            config_path=config,
            initial_search=search,
            tail_lines=tail,
            theme=theme,
            exclude_patterns=exclude_patterns,
        )

        # Run the app
        app.run()

    except KeyboardInterrupt:
        # Clean exit on Ctrl+C
        pass
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
