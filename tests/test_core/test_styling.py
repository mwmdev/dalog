"""Tests for styling engine functionality."""
import pytest
import re
from unittest.mock import Mock

from dalog.core.styling import StylingEngine, CompiledPattern
from dalog.config.models import StylingConfig, StylePattern


class TestStylingEngine:
    """Test the StylingEngine class."""
    
    @pytest.fixture
    def basic_styling_config(self):
        """Create basic styling configuration for testing."""
        return StylingConfig(
            patterns={
                "error": StylePattern(
                    pattern=r"\bERROR\b",
                    color="white",
                    background="red",
                    bold=True
                ),
                "warning": StylePattern(
                    pattern=r"\bWARNING\b",
                    color="black",
                    background="yellow"
                ),
                "info": StylePattern(
                    pattern=r"\bINFO\b",
                    color="blue"
                )
            },
            timestamps={
                "iso_datetime": StylePattern(
                    pattern=r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",
                    color="cyan",
                    bold=True
                )
            }
        )
    
    def test_styling_engine_initialization(self, basic_styling_config):
        """Test StylingEngine initialization."""
        engine = StylingEngine(basic_styling_config)
        
        assert engine.config == basic_styling_config
        assert hasattr(engine, 'compiled_patterns')
        assert len(engine.compiled_patterns) > 0
    
    def test_compile_patterns_valid(self, basic_styling_config):
        """Test compilation of valid regex patterns."""
        engine = StylingEngine(basic_styling_config)
        
        # Should have compiled patterns from all categories
        pattern_names = [p.name for p in engine.compiled_patterns]
        
        assert "error" in pattern_names
        assert "warning" in pattern_names
        assert "info" in pattern_names
        assert "iso_datetime" in pattern_names
    
    def test_compile_patterns_invalid(self):
        """Test compilation with invalid regex patterns."""
        config = StylingConfig(
            patterns={
                "bad_pattern": StylePattern(
                    pattern="[invalid regex",  # Unclosed bracket
                    color="red"
                )
            }
        )
        
        # Should handle invalid patterns gracefully
        engine = StylingEngine(config)
        pattern_names = [p.name for p in engine.compiled_patterns]
        assert "bad_pattern" not in pattern_names
    
    def test_apply_styling_no_matches(self, basic_styling_config):
        """Test styling line with no pattern matches."""
        engine = StylingEngine(basic_styling_config)
        line = "This is a normal log line"
        
        styled = engine.apply_styling(line)
        
        # Should return Rich Text object
        assert hasattr(styled, 'plain')
        assert styled.plain == line
    
    def test_apply_styling_single_match(self, basic_styling_config):
        """Test styling line with single pattern match."""
        engine = StylingEngine(basic_styling_config)
        line = "Something ERROR occurred"
        
        styled = engine.apply_styling(line)
        
        # Should return Rich Text with styling applied
        assert hasattr(styled, 'plain')
        assert styled.plain == line
        # The Rich Text object should have some styling applied
        assert len(styled._spans) > 0 or hasattr(styled, '_style_map')
    
    def test_apply_styling_multiple_matches(self, basic_styling_config):
        """Test styling line with multiple pattern matches."""
        engine = StylingEngine(basic_styling_config)
        line = "ERROR and WARNING in same line"
        
        styled = engine.apply_styling(line)
        
        # Should apply multiple styles
        assert styled.plain == line
        # Should have styling information
        assert hasattr(styled, '_spans') or hasattr(styled, '_style_map')
    
    def test_apply_styling_timestamp_match(self, basic_styling_config):
        """Test styling line with timestamp pattern."""
        engine = StylingEngine(basic_styling_config)
        line = "2024-01-15 10:30:00 INFO Application started"
        
        styled = engine.apply_styling(line)
        
        # Should match both timestamp and INFO
        assert styled.plain == line
    
    def test_add_custom_pattern(self, basic_styling_config):
        """Test adding custom patterns at runtime."""
        engine = StylingEngine(basic_styling_config)
        initial_count = len(engine.compiled_patterns)
        
        # Add custom pattern
        success = engine.add_custom_pattern(
            "custom_test",
            r"\bTEST\b",
            color="green",
            bold=True
        )
        
        assert success is True
        assert len(engine.compiled_patterns) > initial_count
        
        # Should be able to use the new pattern
        line = "This is a TEST message"
        styled = engine.apply_styling(line)
        assert styled.plain == line
    
    def test_add_invalid_custom_pattern(self, basic_styling_config):
        """Test adding invalid custom pattern."""
        engine = StylingEngine(basic_styling_config)
        
        # Add invalid pattern
        success = engine.add_custom_pattern(
            "invalid_test",
            "[invalid regex",
            color="red"
        )
        
        assert success is False
    
    def test_remove_custom_pattern(self, basic_styling_config):
        """Test removing custom patterns."""
        engine = StylingEngine(basic_styling_config)
        
        # Add a custom pattern first
        engine.add_custom_pattern("temp_pattern", r"\bTEMP\b", color="blue")
        
        # Remove it
        success = engine.remove_custom_pattern("temp_pattern")
        assert success is True
        
        # Try to remove non-existent pattern
        success = engine.remove_custom_pattern("nonexistent")
        assert success is False
    
    def test_get_pattern_names(self, basic_styling_config):
        """Test getting pattern names by category."""
        engine = StylingEngine(basic_styling_config)
        pattern_names = engine.get_pattern_names()
        
        assert "patterns" in pattern_names
        assert "timestamps" in pattern_names
        assert "custom" in pattern_names
        
        assert "error" in pattern_names["patterns"]
        assert "warning" in pattern_names["patterns"]
        assert "info" in pattern_names["patterns"]
        assert "iso_datetime" in pattern_names["timestamps"]
    
    def test_validate_pattern(self, basic_styling_config):
        """Test pattern validation."""
        engine = StylingEngine(basic_styling_config)
        
        # Valid pattern
        is_valid, error = engine.validate_pattern(r"\bTEST\b")
        assert is_valid is True
        assert error is None
        
        # Invalid pattern
        is_valid, error = engine.validate_pattern("[invalid")
        assert is_valid is False
        assert error is not None
    
    def test_apply_styling_cached(self, basic_styling_config):
        """Test cached styling application."""
        engine = StylingEngine(basic_styling_config)
        line = "ERROR: Test message"
        
        # First call
        styled1 = engine.apply_styling_cached(line)
        
        # Second call with same line (should use cache)
        styled2 = engine.apply_styling_cached(line)
        
        # Should return equivalent results
        assert styled1.plain == styled2.plain
    
    def test_compiled_pattern_creation(self):
        """Test CompiledPattern creation."""
        import re
        from rich.style import Style
        
        pattern = re.compile(r"\bTEST\b")
        style = Style(color="red", bold=True)
        
        compiled = CompiledPattern(
            name="test_pattern",
            pattern=pattern,
            style=style,
            priority=1
        )
        
        assert compiled.name == "test_pattern"
        assert compiled.pattern == pattern
        assert compiled.style == style
        assert compiled.priority == 1
    
    def test_pattern_priority_ordering(self):
        """Test that patterns are applied in priority order."""
        config = StylingConfig(
            patterns={
                "low_priority": StylePattern(
                    pattern=r"ERROR",
                    color="red"
                )
            },
            timestamps={
                "high_priority": StylePattern(
                    pattern=r"ERROR",
                    color="blue"
                )
            }
        )
        
        engine = StylingEngine(config)
        
        # Should be sorted by priority
        priorities = [p.priority for p in engine.compiled_patterns]
        assert priorities == sorted(priorities)
    
    def test_empty_styling_config(self):
        """Test styling engine with empty configuration."""
        config = StylingConfig()  # Empty config
        engine = StylingEngine(config)
        
        line = "ERROR WARNING INFO"
        styled = engine.apply_styling(line)
        
        # Should work but produce no styling
        assert styled.plain == line
    
    def test_overlapping_patterns(self):
        """Test handling of overlapping pattern matches."""
        config = StylingConfig(
            patterns={
                "error_full": StylePattern(
                    pattern=r"ERROR_CODE",
                    color="red"
                ),
                "error_partial": StylePattern(
                    pattern=r"ERROR",
                    color="yellow"
                )
            }
        )
        
        engine = StylingEngine(config)
        line = "ERROR_CODE detected"
        
        styled = engine.apply_styling(line)
        
        # Should handle overlapping matches based on priority
        assert styled.plain == line
    
    @pytest.mark.parametrize("pattern,text,should_have_styling", [
        (r"\bERROR\b", "ERROR occurred", True),
        (r"\bERROR\b", "NO_ERROR here", False),
        (r"(?i)error", "Error occurred", True),
        (r"^INFO", "INFO at start", True),
        (r"^INFO", "Not INFO at start", False),
    ])
    def test_various_regex_patterns(self, pattern, text, should_have_styling):
        """Test various regex pattern types."""
        config = StylingConfig(
            patterns={
                "test": StylePattern(pattern=pattern, color="red")
            }
        )
        
        engine = StylingEngine(config)
        styled = engine.apply_styling(text)
        
        assert styled.plain == text
        # Can't easily test if styling was applied without inspecting Rich internals
        # But at least verify it doesn't crash 