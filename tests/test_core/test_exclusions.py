"""Tests for exclusion management functionality."""
import pytest
from unittest.mock import Mock

from dalog.core.exclusions import ExclusionManager


class TestExclusionManager:
    """Test the ExclusionManager class."""
    
    def test_init_empty(self):
        """Test initializing ExclusionManager with no patterns."""
        manager = ExclusionManager()
        
        assert manager.patterns == []
        assert manager.is_regex is True  # Default
        # case_sensitive removed - always case sensitive now
        assert manager.get_excluded_count() == 0
    
    def test_init_with_patterns(self):
        """Test initializing ExclusionManager with patterns."""
        patterns = ["DEBUG:", "TRACE:"]
        manager = ExclusionManager(
            patterns=patterns,
            is_regex=False,
        )
        
        assert manager.patterns == patterns
        assert manager.is_regex is False
    
    def test_add_pattern(self):
        """Test adding exclusion patterns."""
        manager = ExclusionManager()
        
        result = manager.add_pattern("ERROR:")
        assert result is True
        assert "ERROR:" in manager.patterns
        assert len(manager.patterns) == 1
        
        result = manager.add_pattern("WARNING:")
        assert result is True
        assert len(manager.patterns) == 2
        assert "WARNING:" in manager.patterns
    
    def test_add_duplicate_pattern(self):
        """Test adding duplicate patterns."""
        manager = ExclusionManager()
        
        result = manager.add_pattern("DEBUG:")
        assert result is True
        result = manager.add_pattern("DEBUG:")  # Duplicate
        assert result is False
        
        # Should not add duplicates
        assert len(manager.patterns) == 1
        assert manager.patterns.count("DEBUG:") == 1
    
    def test_remove_pattern(self):
        """Test removing exclusion patterns."""
        manager = ExclusionManager(patterns=["DEBUG:", "TRACE:"])
        
        manager.remove_pattern("DEBUG:")
        assert "DEBUG:" not in manager.patterns
        assert "TRACE:" in manager.patterns
        assert len(manager.patterns) == 1
    
    def test_remove_nonexistent_pattern(self):
        """Test removing pattern that doesn't exist."""
        manager = ExclusionManager(patterns=["DEBUG:"])
        
        # Should not raise error
        manager.remove_pattern("NONEXISTENT:")
        assert len(manager.patterns) == 1
        assert "DEBUG:" in manager.patterns
    
    
    def test_should_exclude_exact_match(self):
        """Test exclusion with exact string matching."""
        manager = ExclusionManager(
            patterns=["DEBUG:", "TRACE:"],
            is_regex=False,
        )
        
        # Should exclude lines containing patterns
        assert manager.should_exclude("2024-01-15 DEBUG: Loading config")
        assert manager.should_exclude("TRACE: Function called")
        
        # Should not exclude lines without patterns
        assert not manager.should_exclude("2024-01-15 INFO: Application started")
        assert not manager.should_exclude("2024-01-15 ERROR: Connection failed")
    
    def test_should_exclude_case_sensitivity_behavior(self):
        """Test that exclusions are now always case sensitive."""
        manager = ExclusionManager(
            patterns=["debug:", "trace:"],
            is_regex=False,
        )
        
        # Should exclude exact case matches
        assert manager.should_exclude("debug: Loading config")
        assert manager.should_exclude("debug: loading config")
        assert manager.should_exclude("trace: Function called")
        
        # Should NOT exclude different case (now always case sensitive)
        assert not manager.should_exclude("DEBUG: Loading config")
        assert not manager.should_exclude("Debug: Loading Config")
        assert not manager.should_exclude("TRACE: Function called")
    
    def test_should_exclude_case_sensitive(self):
        """Test case sensitive exclusion."""
        manager = ExclusionManager(
            patterns=["DEBUG:"],
            is_regex=False,
        )
        
        # Should only exclude exact case matches
        assert manager.should_exclude("DEBUG: Loading config")
        assert not manager.should_exclude("debug: loading config")
        assert not manager.should_exclude("Debug: Loading Config")
    
    def test_should_exclude_regex_patterns(self):
        """Test exclusion with regex patterns."""
        manager = ExclusionManager(
            patterns=[r"\bDEBUG\b", r"healthcheck.*"],
            is_regex=True,
        )
        
        # Should exclude based on regex
        assert manager.should_exclude("DEBUG message here")
        assert manager.should_exclude("healthcheck endpoint called")
        assert manager.should_exclude("healthcheck-status: OK")
        
        # Should not exclude different case (now case sensitive)
        assert not manager.should_exclude("debug message here")
        assert not manager.should_exclude("HEALTHCHECK endpoint called")
        
        # Should not exclude partial matches without word boundaries
        assert not manager.should_exclude("DEBUGGING mode enabled")  # No word boundary
    
    def test_should_exclude_invalid_regex(self):
        """Test exclusion with invalid regex patterns."""
        manager = ExclusionManager(
            patterns=["[invalid regex", "valid_pattern"],
            is_regex=True
        )
        
        # Should handle invalid regex gracefully
        assert not manager.should_exclude("test [invalid regex content")
        assert manager.should_exclude("test valid_pattern content")
    
    def test_filter_lines_list(self):
        """Test filtering a list of lines."""
        manager = ExclusionManager(
            patterns=["DEBUG:", "TRACE:"],
            is_regex=False
        )
        
        lines = [
            "INFO: Application started",
            "DEBUG: Loading configuration",
            "ERROR: Connection failed",
            "TRACE: Function entry",
            "WARNING: High memory usage"
        ]
        
        filtered = manager.filter_lines(lines)
        
        # Should exclude DEBUG and TRACE lines
        assert len(filtered) == 3
        assert "INFO: Application started" in filtered
        assert "ERROR: Connection failed" in filtered
        assert "WARNING: High memory usage" in filtered
        
        assert "DEBUG: Loading configuration" not in filtered
        assert "TRACE: Function entry" not in filtered
    
    def test_filter_lines_generator(self):
        """Test filtering lines from a generator."""
        manager = ExclusionManager(patterns=["DEBUG:"], is_regex=False)
        
        def line_generator():
            yield "INFO: Application started"
            yield "DEBUG: Loading configuration"
            yield "ERROR: Connection failed"
        
        filtered = list(manager.filter_lines(line_generator()))
        
        assert len(filtered) == 2
        assert "DEBUG: Loading configuration" not in filtered
    
    def test_get_excluded_count_tracking(self):
        """Test tracking of excluded line count."""
        manager = ExclusionManager(patterns=["DEBUG:"], is_regex=False)
        
        lines = [
            "INFO: Application started",
            "DEBUG: Loading config",
            "DEBUG: Another debug line",
            "ERROR: Connection failed"
        ]
        
        # Filter lines
        filtered = manager.filter_lines(lines)
        
        # Should track excluded count
        assert manager.get_excluded_count() == 2
        assert len(filtered) == 2
    
    def test_reset_excluded_count(self):
        """Test resetting excluded count."""
        manager = ExclusionManager(patterns=["DEBUG:"], is_regex=False)
        
        # Exclude some lines first
        lines = ["DEBUG: test1", "DEBUG: test2", "INFO: test"]
        manager.filter_lines(lines)
        
        assert manager.get_excluded_count() == 2
        
        # Reset count
        manager.reset_excluded_count()
        assert manager.get_excluded_count() == 0
    
    def test_multiple_patterns_single_line(self):
        """Test line matching multiple exclusion patterns."""
        manager = ExclusionManager(
            patterns=["DEBUG:", "config"],
            is_regex=False
        )
        
        line = "DEBUG: Loading config file"
        
        # Should exclude if any pattern matches
        assert manager.should_exclude(line)
        
        # Test with only one pattern matching
        line2 = "INFO: Loading config file"
        assert manager.should_exclude(line2)  # Matches "config"
        
        line3 = "DEBUG: Starting application"
        assert manager.should_exclude(line3)  # Matches "DEBUG:"
    
    def test_empty_line_handling(self):
        """Test handling of empty lines."""
        manager = ExclusionManager(patterns=["DEBUG:"], is_regex=False)
        
        # Empty lines should not be excluded
        assert not manager.should_exclude("")
        assert not manager.should_exclude("   ")  # Whitespace only
        
        lines = ["INFO: test", "", "DEBUG: test", "   "]
        filtered = manager.filter_lines(lines)
        
        # Should keep empty lines but exclude DEBUG
        assert len(filtered) == 3
        assert "" in filtered
        assert "   " in filtered
        assert "DEBUG: test" not in filtered
    
    def test_special_characters_in_patterns(self):
        """Test patterns with special characters."""
        manager = ExclusionManager(
            patterns=["[INFO]", "(debug)", "test.log"],
            is_regex=False
        )
        
        # Should match literally, not as regex
        assert manager.should_exclude("2024-01-15 [INFO] Starting app")
        assert manager.should_exclude("Function (debug) called")
        assert manager.should_exclude("Opening test.log file")
        
        # Should not match as regex patterns
        assert not manager.should_exclude("AINFO]")  # Would match [INFO] as regex
    
    def test_unicode_pattern_matching(self):
        """Test pattern matching with Unicode characters."""
        manager = ExclusionManager(
            patterns=["🚨", "ERROR", "Tëst"],
            is_regex=False,
        )
        
        # Should handle Unicode properly
        assert manager.should_exclude("🚨 Alert message")
        assert manager.should_exclude("Unicode Tëst message")
        assert manager.should_exclude("Regular ERROR message")
    
    def test_very_long_lines(self):
        """Test handling of very long lines."""
        manager = ExclusionManager(patterns=["DEBUG:"], is_regex=False)
        
        # Create a very long line
        long_line = "DEBUG: " + "x" * 10000
        
        # Should handle long lines efficiently
        assert manager.should_exclude(long_line)
    
    @pytest.mark.parametrize("regex_pattern,test_line,should_exclude", [
        (r"^\d{4}-\d{2}-\d{2}.*DEBUG", "2024-01-15 DEBUG: test", True),
        (r"^\d{4}-\d{2}-\d{2}.*DEBUG", "DEBUG: 2024-01-15 test", False),
        (r"ERROR|WARN", "ERROR occurred", True),
        (r"ERROR|WARN", "WARN level", True),
        (r"ERROR|WARN", "INFO message", False),
        (r"\bhealthcheck\b", "healthcheck endpoint", True),
        (r"\bhealthcheck\b", "unhealthcheck status", False),
    ])
    def test_regex_pattern_variations(self, regex_pattern, test_line, should_exclude):
        """Test various regex pattern scenarios."""
        manager = ExclusionManager(
            patterns=[regex_pattern],
            is_regex=True
        )
        
        assert manager.should_exclude(test_line) == should_exclude 
    
    def test_init_with_patterns_preserves_settings(self):
        """Test that initialization with patterns preserves is_regex settings."""
        patterns = ["DEBUG:", "TRACE:", "healthcheck"]
        
        # Test with regex=False (always case sensitive now)
        manager = ExclusionManager(patterns=patterns, is_regex=False)
        assert len(manager._patterns) == 3
        for pattern in manager._patterns:
            assert pattern.is_regex == False
            
        # Test with regex=True
        manager2 = ExclusionManager(patterns=patterns, is_regex=True)
        assert len(manager2._patterns) == 3
        for pattern in manager2._patterns:
            assert pattern.is_regex == True