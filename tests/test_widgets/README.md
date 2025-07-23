# DaLog Widget Testing Suite

This directory contains comprehensive tests for the DaLog application's Textual widgets and UI components.

## Overview

The test suite covers:
- **LogViewerWidget**: Search functionality, visual mode, content management
- **ExclusionModal**: Pattern management and UI interactions
- **HeaderWidget**: Status display and reactive properties
- **App Integration**: Keybindings, state management, and component interactions
- **Snapshot Tests**: Visual regression testing (requires pytest-textual-snapshot)

## Test Structure

```
test_widgets/
├── conftest.py                    # Test fixtures and utilities
├── test_log_viewer_widget.py      # LogViewerWidget tests
├── test_exclusion_modal.py        # ExclusionModal tests  
├── test_header_widget.py          # HeaderWidget tests
├── test_app_integration.py        # App-level integration tests
├── test_runner.py                 # Simple test runner
└── README.md                      # This file

../test_snapshots/
└── test_basic_snapshots.py        # Visual regression tests

../fixtures/
├── widget_test_data/              # Test log files
│   ├── unicode_log.txt           # Unicode and international text
│   ├── malformed_log.txt         # Malformed entries
│   ├── multiline_log.txt         # Multiline stack traces
│   ├── large_log.txt             # Performance testing (5000+ lines)
│   └── regex_test_log.txt        # Regex pattern testing
└── mock_configs/                  # Test configurations
    ├── test_keybindings.toml     # Default test config
    └── custom_keybindings.toml   # Custom keybinding config
```

## Running Tests

### Option 1: Using pytest directly
```bash
# Run all widget tests
pytest tests/test_widgets/ -v --asyncio-mode=auto

# Run specific test class
pytest tests/test_widgets/test_log_viewer_widget.py::TestLogViewerSearch -v

# Run with coverage
pytest tests/test_widgets/ --cov=src/dalog/widgets --cov-report=html
```

### Option 2: Using the test runner
```bash
# Simple test runner that handles configuration
python tests/test_widgets/test_runner.py
```

### Option 3: From project root
```bash
# Run all tests including widgets
pytest tests/ -v --asyncio-mode=auto

# Skip snapshot tests if pytest-textual-snapshot not available
pytest tests/ -v --asyncio-mode=auto -k "not snapshot"
```

## Test Dependencies

### Required
- `pytest>=7.0.0`
- `pytest-asyncio>=0.21.0` 
- `textual` (the application dependency)

### Optional
- `pytest-textual-snapshot>=0.4.0` - For visual regression testing
- `pytest-mock>=3.10.0` - Enhanced mocking (uses unittest.mock by default)
- `pytest-cov>=4.0.0` - Code coverage reporting

### Installing Test Dependencies
```bash
# Install required dependencies
pip install pytest pytest-asyncio

# Install optional dependencies for full test suite
pip install pytest-textual-snapshot pytest-mock pytest-cov
```

## Test Categories

### Unit Tests

#### LogViewerWidget Tests (`test_log_viewer_widget.py`)
- **Search functionality**: Live search, regex patterns, case sensitivity
- **Visual mode**: Vi-style navigation, selection, clipboard integration
- **Content management**: Loading from LogProcessor, refresh, line counts
- **Reactive properties**: Search term, visual mode state, line counts

#### ExclusionModal Tests (`test_exclusion_modal.py`) 
- **Modal behavior**: Open/close, focus management, escape handling
- **Pattern management**: Add/remove patterns, regex validation
- **UI interactions**: Button clicks, keyboard shortcuts, input validation
- **Integration**: ExclusionManager integration, state consistency

#### HeaderWidget Tests (`test_header_widget.py`)
- **Status display**: File information, line counts, search status
- **Reactive properties**: Property updates, watch methods
- **Edge cases**: Large files, special characters, formatting

### Integration Tests

#### App Integration Tests (`test_app_integration.py`)
- **Keybinding integration**: Configurable keys, mode-aware navigation
- **Visual mode integration**: Complete workflow testing
- **File operations**: Loading, reload, live monitoring
- **State management**: Search persistence, modal isolation
- **Error handling**: Clipboard errors, invalid regex, file access

### Snapshot Tests

#### Visual Regression Tests (`test_basic_snapshots.py`)
- **Widget appearance**: Default states, themed appearance
- **Interactive states**: Search active, visual mode, selections
- **Modal dialogs**: Exclusion modal, help screen
- **Responsive layouts**: Different terminal sizes
- **Theme variations**: Different color schemes (when available)

## Test Fixtures

### Mock Objects
- `mock_config`: Test configuration with default settings
- `mock_log_processor`: LogProcessor with sample data
- `mock_exclusion_manager`: ExclusionManager with test patterns
- `mock_styling_engine`: StylingEngine with basic styling
- `mock_pyperclip`: Clipboard operations mock

### Test Data
- `sample_log_content`: Basic log entries for standard testing
- `large_log_content`: 1000+ lines for performance testing
- `unicode_log_content`: International text and emoji testing
- `malformed_log_content`: Invalid entries for error handling
- `multiline_log_content`: Stack traces and JSON for complex parsing
- `regex_test_log_content`: Patterns for regex testing

### File Fixtures
- `temp_log_file`: Temporary file with sample content
- `large_temp_log_file`: Large temporary file for performance
- `test_config_file`: Test configuration TOML
- `custom_config_file`: Alternative configuration

## Testing Best Practices

### Widget Testing
1. Use `App.run_test()` and `Pilot` for Textual widget testing
2. Mock external dependencies (file system, clipboard, SSH)
3. Test reactive properties independently
4. Verify UI state changes with `pilot.pause()`

### Async Testing
1. All test methods are `async` and use `await pilot.pause()`
2. Tests use `pytest-asyncio` with `asyncio_mode="auto"`
3. Mock async operations with `AsyncMock`

### Mocking Strategy
1. Mock at the boundary (LogProcessor, ExclusionManager, etc.)
2. Use `spec=` parameter to ensure mock interface matches
3. Patch external libraries (pyperclip, paramiko, watchdog)
4. Create predictable test data with mock returns

### Test Organization
1. Group tests by functionality using classes
2. Use descriptive test names that explain what is tested
3. Include both positive and negative test cases
4. Test edge cases and error conditions

## Performance Testing

The test suite includes performance tests for:
- Large file handling (5000+ lines)
- Memory usage monitoring
- Search performance with large datasets
- Visual mode navigation speed
- Content refresh performance

## Snapshot Testing

Visual regression tests capture widget appearance as SVG images:
- Requires `pytest-textual-snapshot` package
- Run with `--snapshot-update` to update golden images
- Tests automatically skip if snapshot plugin unavailable
- Covers default appearance, interactive states, and responsive layouts

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure `src/dalog` is in Python path (handled by conftest.py)
2. **Async Errors**: Use `pytest-asyncio` and `--asyncio-mode=auto`
3. **Mock Failures**: Check mock specifications match actual interfaces
4. **Snapshot Failures**: Update with `--snapshot-update` after visual changes

### Debug Tips

1. Use `pytest -v -s` for verbose output and print statements
2. Add `await pilot.pause(delay=0.1)` for timing issues
3. Use `pytest --pdb` to drop into debugger on failures
4. Check mock call history: `mock.call_args_list`

### Test Isolation

1. Each test runs in isolated app instance
2. Mocks are reset between tests
3. Temporary files are cleaned up automatically
4. No shared state between test methods

## Contributing

When adding new tests:
1. Follow the existing naming conventions
2. Add appropriate fixtures for new test data
3. Mock external dependencies appropriately
4. Include both unit and integration test coverage
5. Add snapshot tests for visual components
6. Update this README for significant changes

## Coverage Goals

- **Unit Tests**: 90%+ coverage for widget code
- **Integration Tests**: All major user workflows
- **Edge Cases**: Error conditions and boundary cases
- **Performance**: Large file and memory testing
- **Visual**: Snapshot coverage for UI regressions