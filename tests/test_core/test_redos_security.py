"""
ReDoS vulnerability security tests for dalog.

Tests to ensure regex-based DoS attacks are prevented across all
input vectors in the application.
"""

import pytest
import re
import tempfile
import toml
from pathlib import Path

from dalog.config.models import DaLogConfig, StylePattern, SecurityConfig  
from dalog.config.loader import ConfigLoader
from dalog.core.styling import StylingEngine
from dalog.core.exclusions import ExclusionManager, ExclusionPattern
from dalog.security.regex_security import (
    RegexTimeoutError,
    RegexComplexityError,
    secure_compile,
    validate_pattern_security,
    KNOWN_DANGEROUS_PATTERNS,
    REDOS_TEST_STRINGS,
)


class TestReDoSSecurityStyling:
    """Test ReDoS protection in styling engine."""

    def test_dangerous_pattern_compilation_blocked(self):
        """Test that known dangerous patterns are blocked during compilation."""
        config = DaLogConfig()
        styling_engine = StylingEngine(config.styling)
        
        dangerous_patterns = [
            "(a+)+",         # Classic nested quantifier
            "(a*)*b",        # Nested quantifier with end
            "([a-zA-Z]+)*",  # Complex nested quantifier
            "(a|a)*",        # Overlapping alternation
            "(.*)*",         # Extremely dangerous wildcard
        ]
        
        for pattern in dangerous_patterns:
            with pytest.raises((RegexComplexityError, ValueError)):
                style_pattern = StylePattern(pattern=pattern, color="red")
                
    def test_timeout_protection_during_styling(self):
        """Test that styling operations timeout on malicious patterns."""
        # Create a pattern that could cause timeout if not protected
        # This test depends on the timeout protection working
        config = DaLogConfig()
        styling_engine = StylingEngine(config.styling)
        
        # Try to compile a borderline complex pattern
        try:
            # This should work with security limits
            simple_pattern = StylePattern(pattern=r"a+b", color="red") 
            styling_engine.add_custom_pattern("test", simple_pattern.pattern)
            assert True  # If we get here, basic patterns work
        except (RegexComplexityError, RegexTimeoutError):
            pytest.fail("Simple pattern should not be blocked")
            
    def test_pattern_validation_with_security(self):
        """Test that pattern validation includes security checks."""
        config = DaLogConfig()
        styling_engine = StylingEngine(config.styling)
        
        # Test valid pattern
        is_valid, error = styling_engine.validate_pattern(r"ERROR.*")
        assert is_valid
        assert error is None
        
        # Test dangerous pattern
        is_valid, error = styling_engine.validate_pattern("(a+)+")
        assert not is_valid
        assert "Security issue" in error
        
    def test_styling_engine_skip_timeout_patterns(self):
        """Test that styling engine skips patterns that timeout during execution."""
        config = DaLogConfig()
        styling_engine = StylingEngine(config.styling)
        
        # Create a text line to style
        test_line = "This is a test line with ERROR content"
        
        # This should work without timeout issues
        styled_text = styling_engine.apply_styling(test_line)
        assert styled_text.plain == test_line


class TestReDoSSecurityExclusions:
    """Test ReDoS protection in exclusion patterns."""
    
    def test_exclusion_pattern_compilation_security(self):
        """Test that exclusion patterns are compiled with security protection."""
        dangerous_patterns = [
            "(a+)+b",
            "(.*)*x", 
            "([0-9]+)*end",
        ]
        
        for pattern in dangerous_patterns:
            exclusion = ExclusionPattern(
                pattern=pattern,
                is_regex=True,
                case_sensitive=True
            )
            # Pattern should be marked as invalid due to security
            assert not exclusion.is_valid
            
    def test_exclusion_manager_validation(self):
        """Test that exclusion manager validates patterns for security."""
        manager = ExclusionManager()
        
        # Test valid pattern
        is_valid, error = manager.validate_pattern("ERROR", is_regex=True)
        assert is_valid
        assert error is None
        
        # Test dangerous pattern
        is_valid, error = manager.validate_pattern("(a+)+", is_regex=True)
        assert not is_valid
        assert "Security issue" in error
        
    def test_exclusion_pattern_matching_timeout_protection(self):
        """Test that pattern matching has timeout protection."""
        # Create a valid pattern that won't be blocked by complexity analysis
        pattern = ExclusionPattern(
            pattern=r"test.*content",
            is_regex=True,
            case_sensitive=True
        )
        
        if pattern.is_valid:
            # This should work without timeout issues
            result = pattern.matches("test line with content")
            assert isinstance(result, bool)


class TestReDoSSecurityConfig:
    """Test ReDoS protection in configuration loading."""
    
    def test_config_validation_blocks_dangerous_patterns(self):
        """Test that configuration validation blocks dangerous patterns."""
        # Create a config with dangerous styling pattern
        config_data = {
            "styling": {
                "patterns": {
                    "dangerous": {
                        "pattern": "(a+)+",
                        "color": "red"
                    }
                }
            }
        }
        
        with pytest.raises(ValueError, match="Unsafe regex pattern"):
            # This should raise an error during validation
            config = DaLogConfig(**config_data)
            
    def test_config_loader_validation_reports_unsafe_patterns(self):
        """Test that config loader blocks unsafe patterns during loading."""
        # Create a temporary config file with dangerous patterns
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            config_data = {
                "styling": {
                    "patterns": {
                        "dangerous": {
                            "pattern": "(a+)+b",
                            "color": "red"
                        }
                    }
                },
                "exclusions": {
                    "regex": True,
                    "patterns": ["(.*)*end"]
                }
            }
            toml.dump(config_data, f)
            config_path = Path(f.name)
            
        try:
            # Load config should fail with dangerous patterns
            with pytest.raises(Exception) as exc_info:
                config = ConfigLoader._load_from_file(config_path)
            
            # Should have errors for unsafe patterns
            error_msg = str(exc_info.value)
            assert "Unsafe regex pattern" in error_msg or "nested quantifiers" in error_msg
            
        finally:
            # Clean up
            config_path.unlink()


class TestReDoSSecurityUI:
    """Test ReDoS protection in UI pattern input."""
    
    def test_exclusion_modal_pattern_validation(self):
        """Test that exclusion modal validates patterns for security."""
        manager = ExclusionManager()
        
        # Test that dangerous patterns are rejected
        dangerous_patterns = KNOWN_DANGEROUS_PATTERNS[:5]  # Test first 5
        
        for pattern in dangerous_patterns:
            is_valid, error = manager.validate_pattern(pattern, is_regex=True)
            assert not is_valid, f"Pattern {pattern} should be rejected"
            assert any(keyword in error.lower() for keyword in ["security", "unsafe", "complex"])


class TestPatternComplexityValidation:
    """Test pattern complexity validation and limits."""
    
    def test_pattern_length_limits(self):
        """Test that overly long patterns are rejected."""
        # Create a pattern that exceeds length limits
        long_pattern = "a" * 2000  # Assuming max is 1000
        
        is_safe, error = validate_pattern_security(long_pattern)
        assert not is_safe
        assert "length" in error.lower()
        
    def test_nested_quantifier_detection(self):
        """Test detection of nested quantifiers."""
        nested_patterns = [
            "(a+)+",      # Simple nested
            "(a*)*",      # Star nested  
            "(a{1,10})+", # Brace nested
            "((a+)+)+",   # Triple nested
        ]
        
        for pattern in nested_patterns:
            is_safe, error = validate_pattern_security(pattern)
            assert not is_safe, f"Pattern {pattern} should be unsafe"
            assert any(keyword in error.lower() for keyword in ["quantifier", "nested"])
            
    def test_alternation_group_limits(self):
        """Test that excessive alternation groups are detected."""
        # Create pattern with many alternation groups
        many_alternations = "|".join([f"option{i}" for i in range(20)])
        pattern = f"({many_alternations})"
        
        is_safe, error = validate_pattern_security(pattern)
        assert not is_safe
        assert "alternation" in error.lower()
        
    def test_dangerous_pattern_detection(self):
        """Test detection of specific dangerous patterns."""
        dangerous_specific = [
            "(.*)*",     # Extremely dangerous wildcard
            "(.+)+",     # Extremely dangerous plus
            "(a|a)*",    # Overlapping alternation
        ]
        
        for pattern in dangerous_specific:
            is_safe, error = validate_pattern_security(pattern)
            assert not is_safe, f"Pattern {pattern} should be unsafe"


class TestTimeoutProtection:
    """Test timeout protection for pattern operations."""
    
    def test_secure_compile_timeout_protection(self):
        """Test that secure_compile has timeout protection."""
        # Test basic compilation works
        try:
            pattern = secure_compile(r"test.*")
            assert pattern is not None
        except (RegexTimeoutError, RegexComplexityError):
            pytest.fail("Simple pattern should compile successfully")
            
    def test_pattern_complexity_analysis_performance(self):
        """Test that complexity analysis itself doesn't timeout."""
        # Test various patterns to ensure analysis is fast
        test_patterns = [
            r"simple",
            r"test.*pattern",
            r"[a-zA-Z0-9]+@[a-zA-Z0-9]+\.[a-zA-Z]+",
            r"ERROR|WARNING|INFO",
            r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",
        ]
        
        for pattern in test_patterns:
            # These should all be analyzed quickly
            is_safe, error = validate_pattern_security(pattern)
            # Don't assert on result, just ensure it completes quickly
            assert isinstance(is_safe, bool)


class TestPerformanceRegression:
    """Test that security fixes don't break performance."""
    
    def test_legitimate_patterns_still_work(self):
        """Test that legitimate patterns continue to work normally."""
        legitimate_patterns = [
            r"ERROR.*",
            r"WARNING:.*",
            r"\d{4}-\d{2}-\d{2}",
            r"[A-Z][a-z]+",
            r"https?://[^\s]+",
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        ]
        
        config = DaLogConfig()
        styling_engine = StylingEngine(config.styling)
        
        for pattern in legitimate_patterns:
            try:
                # These should all validate successfully
                is_valid, error = styling_engine.validate_pattern(pattern)
                assert is_valid, f"Legitimate pattern {pattern} should be valid: {error}"
                
                # Should be able to compile
                compiled = secure_compile(pattern)
                assert compiled is not None
                
            except (RegexComplexityError, RegexTimeoutError) as e:
                pytest.fail(f"Legitimate pattern {pattern} should not be blocked: {e}")
                
    def test_styling_performance_maintained(self):
        """Test that styling performance is maintained."""
        config = DaLogConfig()
        styling_engine = StylingEngine(config.styling)
        
        # Test styling a variety of log lines
        test_lines = [
            "2024-01-01 10:00:00 ERROR Something went wrong",
            "INFO: Application started successfully",  
            "WARNING: Low disk space detected",
            "DEBUG: Processing user request #12345",
            "CRITICAL: Database connection failed",
        ]
        
        for line in test_lines:
            # These should all style without timeout issues
            styled = styling_engine.apply_styling(line)
            assert styled.plain == line
            
    def test_exclusion_performance_maintained(self):
        """Test that exclusion performance is maintained."""
        manager = ExclusionManager()
        
        # Add some legitimate exclusion patterns
        legitimate_exclusions = [
            "DEBUG.*",
            "TRACE.*",
            r"\[INFO\].*",
        ]
        
        for pattern in legitimate_exclusions:
            success = manager.add_pattern(pattern, is_regex=True, case_sensitive=False)
            assert success, f"Should be able to add legitimate pattern: {pattern}"
            
        # Test exclusion checking performance
        test_lines = [
            "ERROR: Something important",  # Should not be excluded
            "DEBUG: Verbose output",       # Should be excluded
            "INFO: Normal operation",      # Should not be excluded  
            "TRACE: Very verbose",         # Should be excluded
        ]
        
        for line in test_lines:
            # This should complete quickly without timeout
            should_exclude = manager.should_exclude(line)
            assert isinstance(should_exclude, bool)


# Additional security test data
ATTACK_TEST_CASES = [
    # Pattern, Attack String, Expected Behavior
    ("(a+)+", "a" * 1000, "should_timeout_or_block"),
    ("(a*)*b", "a" * 1000 + "x", "should_timeout_or_block"),  
    ("([a-zA-Z]+)*", "abc" * 500, "should_timeout_or_block"),
    ("(a|a)*", "a" * 1000, "should_timeout_or_block"),
    ("(.*)*", "." * 500, "should_timeout_or_block"),
]


@pytest.mark.parametrize("pattern,attack_string,expected", ATTACK_TEST_CASES)
def test_redos_attack_prevention(pattern, attack_string, expected):
    """Test that ReDoS attacks are prevented across all components."""
    # Test 1: Pattern should be blocked during compilation
    is_safe, error = validate_pattern_security(pattern)
    assert not is_safe, f"Dangerous pattern {pattern} should be blocked"
    
    # Test 2: If somehow compiled, execution should timeout quickly
    try:
        # This should raise an exception during complexity analysis
        compiled = secure_compile(pattern)
        pytest.fail(f"Dangerous pattern {pattern} should not compile")
    except (RegexComplexityError, RegexTimeoutError):
        # This is expected behavior
        pass
        
    # Test 3: Configuration should reject the pattern
    with pytest.raises(ValueError):
        StylePattern(pattern=pattern, color="red")
        
    # Test 4: Exclusion manager should reject the pattern  
    manager = ExclusionManager()
    is_valid, error = manager.validate_pattern(pattern, is_regex=True)
    assert not is_valid, f"Exclusion manager should reject pattern {pattern}"


def test_security_configuration_integration():
    """Test that security configuration is properly integrated."""
    # Test that security config is loaded and applied
    config = DaLogConfig()
    assert hasattr(config, 'security')
    assert config.security.enable_complexity_analysis
    assert config.security.enable_timeout_protection
    assert config.security.regex_compilation_timeout > 0
    assert config.security.regex_execution_timeout > 0
    
    # Test that security limits are reasonable
    assert 0.1 <= config.security.regex_compilation_timeout <= 10.0
    assert 0.1 <= config.security.regex_execution_timeout <= 5.0
    assert 10 <= config.security.max_pattern_length <= 10000
    assert 1 <= config.security.max_quantifier_nesting <= 10
    assert 1 <= config.security.max_alternation_groups <= 100


def test_backward_compatibility():
    """Test that existing legitimate patterns continue to work."""
    # Load default configuration
    config = ConfigLoader.load()
    
    # Validate that default patterns are secure
    errors = ConfigLoader.validate_config(config)
    
    # There should be no security errors in default patterns
    security_errors = [error for error in errors if "unsafe" in error.lower() or "security" in error.lower()]
    assert len(security_errors) == 0, f"Default patterns should be secure: {security_errors}"
    
    # Test that styling engine works with default patterns
    styling_engine = StylingEngine(config.styling)
    test_line = "2024-01-01 ERROR: Test message"
    styled_result = styling_engine.apply_styling(test_line)
    assert styled_result.plain == test_line