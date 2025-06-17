"""Integration tests for dalog components working together."""
import pytest
import tempfile
import time
import gc
from pathlib import Path
from unittest.mock import Mock, patch

from dalog.core.log_processor import LogProcessor
from dalog.core.file_watcher import AsyncFileWatcher
from dalog.core.exclusions import ExclusionManager
from dalog.core.styling import StylingEngine
from dalog.core.html_processor import HTMLProcessor
from dalog.config import get_default_config
from dalog.config.models import HtmlConfig


class TestLogProcessorIntegration:
    """Test LogProcessor integration with other components."""
    
    def test_log_processor_with_exclusions(self):
        """Test LogProcessor working with ExclusionManager."""
        # Create test log content
        content = """2024-01-15 10:30:00 INFO Starting application
2024-01-15 10:30:01 DEBUG Loading configuration
2024-01-15 10:30:02 ERROR Connection failed
2024-01-15 10:30:03 DEBUG Processing request
2024-01-15 10:30:04 INFO Application ready"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)
        
        try:
            # Create processor and exclusion manager
            processor = LogProcessor(temp_path)
            exclusion_manager = ExclusionManager(
                patterns=["DEBUG"],
                is_regex=False,
                case_sensitive=False
            )
            
            with processor:
                lines = list(processor.read_lines())
                
            # Filter lines through exclusion manager
            filtered_lines = exclusion_manager.filter_lines([line.content for line in lines])
            
            # Should have filtered out DEBUG lines
            assert len(filtered_lines) == 3  # INFO, ERROR, INFO
            assert all("DEBUG" not in line for line in filtered_lines)
            assert exclusion_manager.get_excluded_count() == 2
            
        finally:
            temp_path.unlink()
    
    def test_log_processor_with_styling(self):
        """Test LogProcessor working with StylingEngine."""
        content = """2024-01-15 10:30:00 INFO Starting application
2024-01-15 10:30:01 ERROR Connection failed
2024-01-15 10:30:02 WARNING High memory usage"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)
        
        try:
            # Create processor and styling engine
            processor = LogProcessor(temp_path)
            config = get_default_config()
            styling_engine = StylingEngine(config.styling)
            
            with processor:
                lines = list(processor.read_lines())
            
            # Apply styling to each line
            styled_lines = []
            for line in lines:
                styled = styling_engine.apply_styling(line.content)
                styled_lines.append(styled)
            
            # Verify styling was applied
            assert len(styled_lines) == 3
            for styled_line in styled_lines:
                assert hasattr(styled_line, 'plain')
                assert styled_line.plain in [line.content for line in lines]
                
        finally:
            temp_path.unlink()
    
    def test_full_pipeline_integration(self):
        """Test the full processing pipeline: LogProcessor -> Exclusions -> Styling."""
        content = """2024-01-15 10:30:00 INFO Starting application server
2024-01-15 10:30:01 DEBUG Loading configuration from file
2024-01-15 10:30:02 ERROR Failed to connect to database
2024-01-15 10:30:03 DEBUG Retrying connection
2024-01-15 10:30:04 WARNING High memory usage detected
2024-01-15 10:30:05 INFO Application ready to accept requests"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)
        
        try:
            # Create all components
            processor = LogProcessor(temp_path)
            exclusion_manager = ExclusionManager(
                patterns=["DEBUG"],
                is_regex=False
            )
            config = get_default_config()
            styling_engine = StylingEngine(config.styling)
            
            # Full pipeline
            with processor:
                raw_lines = list(processor.read_lines())
            
            # Filter lines
            filtered_lines = exclusion_manager.filter_lines([line.content for line in raw_lines])
            
            # Apply styling
            styled_lines = []
            for line in filtered_lines:
                styled = styling_engine.apply_styling(line)
                styled_lines.append(styled)
            
            # Verify results
            assert len(raw_lines) == 6  # Original lines
            assert len(filtered_lines) == 4  # After filtering DEBUG
            assert len(styled_lines) == 4  # After styling
            assert exclusion_manager.get_excluded_count() == 2
            
            # Verify no DEBUG lines remain
            for line in filtered_lines:
                assert "DEBUG" not in line
            
            # Verify styling is applied
            for styled_line in styled_lines:
                assert hasattr(styled_line, 'plain')
                
        finally:
            temp_path.unlink()


class TestFileWatcherIntegration:
    """Test AsyncFileWatcher integration with other components."""
    
    def test_file_watcher_setup(self):
        """Test basic file watcher setup and teardown."""
        watcher = AsyncFileWatcher()
        
        # Create a test file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write("initial content\n")
            temp_path = Path(f.name)
        
        try:
            # Add file to watcher
            watcher.add_file(temp_path)
            assert temp_path in watcher._watched_files
            
            # Remove file from watcher
            watcher.remove_file(temp_path)
            assert temp_path not in watcher._watched_files
            
        finally:
            temp_path.unlink()
    
    def test_file_watcher_with_callback(self):
        """Test file watcher with callback functionality."""
        watcher = AsyncFileWatcher()
        
        # Create test file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write("initial content\n")
            temp_path = Path(f.name)
        
        try:
            # Test file watcher basic functionality
            watcher.add_file(temp_path)
            assert temp_path in watcher._watched_files
            
            # Test file removal
            removed = watcher.remove_file(temp_path)
            assert removed is True
            assert temp_path not in watcher._watched_files
            
            # Test removing non-existent file
            removed = watcher.remove_file(Path("nonexistent.log"))
            assert removed is False
                
        finally:
            temp_path.unlink()


class TestConfigurationIntegration:
    """Test configuration integration across components."""
    
    def test_config_loading_and_usage(self):
        """Test that configuration loads and works with all components."""
        # Load default configuration
        config = get_default_config()
        
        # Test that config can be used with different components
        styling_engine = StylingEngine(config.styling)
        
        # Test that exclusion config can be used
        exclusion_manager = ExclusionManager(
            patterns=config.exclusions.patterns,
            is_regex=config.exclusions.regex,
            case_sensitive=config.exclusions.case_sensitive
        )
        
        # Test basic functionality
        test_line = "2024-01-15 ERROR Connection failed"
        styled = styling_engine.apply_styling(test_line)
        assert styled.plain == test_line
        
        # Test exclusion (should not exclude ERROR by default)
        assert not exclusion_manager.should_exclude(test_line)
    
    def test_config_validation_integration(self):
        """Test configuration validation works across the system."""
        from dalog.config import ConfigLoader
        
        # Load and validate default config
        config = get_default_config()
        errors = ConfigLoader.validate_config(config)
        
        # Should have no validation errors
        assert len(errors) == 0
        
        # Test that validated config works with components
        styling_engine = StylingEngine(config.styling)
        
        # Test with actual log content
        test_content = "2024-01-15 10:30:00 INFO Application started"
        styled = styling_engine.apply_styling(test_content)
        assert styled.plain == test_content


class TestPerformanceBasics:
    """Basic performance tests for integration scenarios."""
    
    @pytest.mark.parametrize("line_count,max_time", [
        (100, 0.1),      # Small file: 100 lines in <0.1s
        (1000, 0.5),     # Medium file: 1000 lines in <0.5s  
        (5000, 2.0),     # Large file: 5000 lines in <2.0s
    ])
    def test_file_processing_performance(self, line_count, max_time):
        """Test processing performance with different file sizes."""
        # Generate test content
        lines = []
        for i in range(line_count):
            level = ["INFO", "DEBUG", "ERROR", "WARNING"][i % 4]
            lines.append(f"2024-01-15 10:30:{i:02d} {level} Processing request {i}")
        
        content = "\n".join(lines)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)
        
        try:
            processor = LogProcessor(temp_path)
            
            # Measure processing time
            start_time = time.time()
            with processor:
                processed_lines = list(processor.read_lines())
            end_time = time.time()
            
            # Performance assertions
            assert len(processed_lines) == line_count
            processing_time = end_time - start_time
            assert processing_time < max_time, f"Processing {line_count} lines took {processing_time:.3f}s, expected <{max_time}s"
            
        finally:
            temp_path.unlink()
    
    @pytest.mark.parametrize("tail_size,total_lines", [
        (10, 1000),      # Tail 10 from 1000 lines
        (100, 1000),     # Tail 100 from 1000 lines
        (500, 1000),     # Tail 500 from 1000 lines
        (50, 10000),     # Tail 50 from 10000 lines
    ])
    def test_tail_processing_performance(self, tail_size, total_lines):
        """Test tail processing performance with different sizes."""
        # Generate test content
        lines = []
        for i in range(total_lines):
            lines.append(f"2024-01-15 10:30:{i:02d} INFO Line {i}")
        
        content = "\n".join(lines)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)
        
        try:
            processor = LogProcessor(temp_path, tail_lines=tail_size)
            
            start_time = time.time()
            with processor:
                tail_lines = list(processor.read_lines())
            end_time = time.time()
            
            # Should get the correct tail size
            assert len(tail_lines) == tail_size
            
            # Should be fast regardless of total file size
            processing_time = end_time - start_time
            assert processing_time < 1.0, f"Tail processing took {processing_time:.3f}s, expected <1.0s"
            
            # Verify we got the last lines
            assert f"Line {total_lines - 1}" in tail_lines[-1].content
            
        finally:
            temp_path.unlink()
    
    @pytest.mark.parametrize("pattern_count,line_count,expected_time", [
        (10, 1000, 0.1),    # 10 patterns, 1000 lines
        (50, 1000, 0.2),    # 50 patterns, 1000 lines
        (100, 1000, 0.5),   # 100 patterns, 1000 lines
        (10, 5000, 0.2),    # 10 patterns, 5000 lines
    ])
    def test_exclusion_performance_scaling(self, pattern_count, line_count, expected_time):
        """Test exclusion performance with varying pattern and line counts."""
        # Create exclusion patterns
        patterns = [f"DEBUG_{i}" for i in range(pattern_count)]
        exclusion_manager = ExclusionManager(patterns=patterns, is_regex=False)
        
        # Create test lines (every 10th line matches a pattern)
        test_lines = []
        for i in range(line_count):
            if i % 10 == 0:
                test_lines.append(f"DEBUG_{i % pattern_count} test message")
            else:
                test_lines.append(f"INFO test message {i}")
        
        # Measure exclusion performance
        start_time = time.time()
        filtered_lines = exclusion_manager.filter_lines(test_lines)
        end_time = time.time()
        
        # Performance assertions
        processing_time = end_time - start_time
        assert processing_time < expected_time, f"Exclusion took {processing_time:.3f}s, expected <{expected_time}s"
        
        # Verify correct exclusion count
        expected_excluded = line_count // 10
        assert exclusion_manager.get_excluded_count() == expected_excluded
    
    def test_memory_usage_large_file(self):
        """Test that large file processing doesn't consume excessive memory."""
        try:
            import psutil
            import os
        except ImportError:
            pytest.skip("psutil not available for memory testing")
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Generate a large file (10,000 lines)
        lines = []
        for i in range(10000):
            lines.append(f"2024-01-15 10:30:{i:02d} INFO Large file processing test line {i} with some additional content to make lines longer")
        
        content = "\n".join(lines)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)
        
        try:
            processor = LogProcessor(temp_path)
            
            # Process the file
            with processor:
                processed_lines = list(processor.read_lines())
            
            # Check memory usage after processing
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory
            
            # Should not increase memory by more than 50MB for 10k lines
            assert memory_increase < 50, f"Memory increased by {memory_increase:.1f}MB, expected <50MB"
            assert len(processed_lines) == 10000
            
        finally:
            temp_path.unlink()
    
    def test_concurrent_processing_performance(self):
        """Test performance with multiple components working simultaneously."""
        import threading
        
        # Create test data
        content = "\n".join([
            f"2024-01-15 10:30:{i:02d} {['INFO', 'DEBUG', 'ERROR', 'WARNING'][i % 4]} Message {i}"
            for i in range(2000)
        ])
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)
        
        try:
            results = {}
            
            def process_with_exclusions():
                processor = LogProcessor(temp_path)
                exclusion_manager = ExclusionManager(patterns=["DEBUG"], is_regex=False)
                
                start_time = time.time()
                with processor:
                    lines = list(processor.read_lines())
                filtered_lines = exclusion_manager.filter_lines([line.content for line in lines])
                end_time = time.time()
                
                results['exclusions'] = {
                    'time': end_time - start_time,
                    'lines': len(filtered_lines)
                }
            
            def process_with_styling():
                processor = LogProcessor(temp_path)
                config = get_default_config()
                styling_engine = StylingEngine(config.styling)
                
                start_time = time.time()
                with processor:
                    lines = list(processor.read_lines())
                styled_lines = [styling_engine.apply_styling(line.content) for line in lines]
                end_time = time.time()
                
                results['styling'] = {
                    'time': end_time - start_time,
                    'lines': len(styled_lines)
                }
            
            # Run both processes concurrently
            thread1 = threading.Thread(target=process_with_exclusions)
            thread2 = threading.Thread(target=process_with_styling)
            
            overall_start = time.time()
            thread1.start()
            thread2.start()
            
            thread1.join()
            thread2.join()
            overall_end = time.time()
            
            # Both should complete successfully
            assert 'exclusions' in results
            assert 'styling' in results
            
            # Each process should be reasonably fast
            assert results['exclusions']['time'] < 1.0
            assert results['styling']['time'] < 1.0
            
            # Overall time should be reasonable for concurrent processing
            total_time = overall_end - overall_start
            assert total_time < 2.0
            
        finally:
            temp_path.unlink()


class TestStringBasedComponents:
    """Test components that can work with string data without file I/O."""
    
    @pytest.mark.parametrize("patterns,test_lines,expected_excluded", [
        (["ERROR"], ["INFO: ok", "ERROR: bad", "DEBUG: test"], 1),
        (["DEBUG", "TRACE"], ["INFO: ok", "DEBUG: test", "TRACE: detail", "ERROR: bad"], 2),
        (["\\d{4}-\\d{2}-\\d{2}"], ["2024-01-15 INFO: ok", "INFO: no date", "2024-01-16 ERROR: bad"], 2),
    ])
    def test_exclusion_manager_string_processing(self, patterns, test_lines, expected_excluded):
        """Test ExclusionManager with string data (no file I/O)."""
        exclusion_manager = ExclusionManager(
            patterns=patterns,
            is_regex=True,
            case_sensitive=False
        )
        
        filtered_lines = exclusion_manager.filter_lines(test_lines)
        
        assert exclusion_manager.get_excluded_count() == expected_excluded
        assert len(filtered_lines) == len(test_lines) - expected_excluded
    
    @pytest.mark.parametrize("log_level,should_have_styling", [
        ("ERROR", True),
        ("WARNING", True), 
        ("INFO", True),
        ("DEBUG", True),
        ("PLAIN", False),
    ])
    def test_styling_engine_string_processing(self, log_level, should_have_styling):
        """Test StylingEngine with string data (no file I/O)."""
        config = get_default_config()
        styling_engine = StylingEngine(config.styling)
        
        test_line = f"2024-01-15 10:30:00 {log_level} Test message content"
        styled = styling_engine.apply_styling(test_line)
        
        # Should always return properly formatted Rich Text
        assert hasattr(styled, 'plain')
        assert styled.plain == test_line
        
        # For known log levels, there might be styling spans
        if should_have_styling and hasattr(styled, '_spans'):
            # This is hard to test precisely without inspecting Rich internals
            # Just verify it doesn't crash and returns expected structure
            assert isinstance(styled._spans, list)
    
    def test_html_processor_string_processing(self):
        """Test HTMLProcessor with string data (no file I/O)."""
        config = HtmlConfig(enabled_tags=["b", "strong"], strip_unknown_tags=True)
        processor = HTMLProcessor(config)
        
        test_cases = [
            "Plain text log line",
            "Log with <b>bold</b> content", 
            "Remove <script>dangerous</script> but keep <strong>safe</strong>",
            "2024-01-15 ERROR: <em>Emphasized</em> error message"
        ]
        
        for test_line in test_cases:
            result = processor.process_line(test_line)
            # Should not crash and return a string
            assert isinstance(result, str)
            # Should handle HTML appropriately
            if "<script>" in test_line:
                assert "<script>" not in result  # Should be stripped
            if "<b>" in test_line or "<strong>" in test_line:
                # Should preserve enabled tags
                assert "<b>" in result or "<strong>" in result


@pytest.mark.slow
class TestProductionScaleLargeFiles:
    """
    Test handling of production-scale large log files.
    
    These tests are marked as 'slow' and can be run with: pytest -m slow
    They test truly large files (50K-500K lines) to ensure dalog can handle
    real-world production log files efficiently.
    """
    
    def generate_large_log_content(self, line_count, include_variety=True):
        """Generate realistic large log file content."""
        lines = []
        
        # More realistic log patterns and content
        patterns = [
            "2024-01-{day:02d} {hour:02d}:{minute:02d}:{second:02d} INFO [app.server] Processing request {req_id}",
            "2024-01-{day:02d} {hour:02d}:{minute:02d}:{second:02d} DEBUG [app.database] Connection pool status: active={active}, idle={idle}",
            "2024-01-{day:02d} {hour:02d}:{minute:02d}:{second:02d} ERROR [app.auth] Authentication failed for user {user} from IP {ip}",
            "2024-01-{day:02d} {hour:02d}:{minute:02d}:{second:02d} WARNING [app.memory] Memory usage {memory}MB exceeds threshold",
            "2024-01-{day:02d} {hour:02d}:{minute:02d}:{second:02d} TRACE [app.cache] Cache miss for key: {key}",
            "2024-01-{day:02d} {hour:02d}:{minute:02d}:{second:02d} SUCCESS [app.payment] Payment processed: transaction_id={tx_id}, amount=${amount}",
        ]
        
        for i in range(line_count):
            if include_variety:
                pattern = patterns[i % len(patterns)]
                
                # Generate realistic variable data
                line = pattern.format(
                    day=15 + (i // 10000) % 15,  # Spread across days
                    hour=8 + (i // 3600) % 16,   # Business hours
                    minute=(i // 60) % 60,
                    second=i % 60,
                    req_id=f"req-{i:08d}",
                    active=5 + (i % 20),
                    idle=10 + (i % 15),  
                    user=f"user{i % 100:03d}",
                    ip=f"192.168.{(i % 254) + 1}.{((i * 7) % 254) + 1}",
                    memory=512 + (i % 1024),
                    key=f"cache_key_{i % 1000:04d}",
                    tx_id=f"tx-{i:010d}",
                    amount=f"{(i % 10000) / 100:.2f}"
                )
            else:
                # Simple format for performance tests
                level = ["INFO", "DEBUG", "ERROR", "WARNING"][i % 4]
                line = f"2024-01-15 10:{(i//3600)%24:02d}:{(i//60)%60:02d} {level} Log entry number {i}"
                
            lines.append(line)
            
        return "\n".join(lines)
    
    @pytest.mark.parametrize("line_count,max_processing_time", [
        (50000, 5.0),    # 50K lines (~5MB) in <5s
        (100000, 10.0),  # 100K lines (~10MB) in <10s
        (250000, 25.0),  # 250K lines (~25MB) in <25s
    ])
    def test_large_file_processing_performance(self, line_count, max_processing_time):
        """Test processing performance with truly large files."""
        # Generate large log content
        content = self.generate_large_log_content(line_count, include_variety=False)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)
            
        # Force garbage collection before test
        gc.collect()
        
        try:
            processor = LogProcessor(temp_path)
            
            # Measure processing time
            start_time = time.time()
            with processor:
                processed_lines = list(processor.read_lines())
            end_time = time.time()
            
            processing_time = end_time - start_time
            
            # Verify correctness
            assert len(processed_lines) == line_count
            assert processing_time < max_processing_time, (
                f"Processing {line_count} lines took {processing_time:.2f}s, "
                f"expected <{max_processing_time}s"
            )
            
            # Log performance for analysis
            lines_per_second = line_count / processing_time
            print(f"\nProcessed {line_count} lines in {processing_time:.2f}s "
                  f"({lines_per_second:.0f} lines/sec)")
            
        finally:
            temp_path.unlink()
            gc.collect()
    
    @pytest.mark.parametrize("file_size_lines,tail_size", [
        (100000, 50),     # Tail 50 from 100K lines
        (250000, 100),    # Tail 100 from 250K lines
        (500000, 1000),   # Tail 1000 from 500K lines
        (1000000, 500),   # Tail 500 from 1M lines
    ])
    def test_gigabyte_scale_tail_performance(self, file_size_lines, tail_size):
        """Test tail performance on very large files (approaching GB scale)."""
        # Generate large content
        content = self.generate_large_log_content(file_size_lines, include_variety=False)
        file_size_mb = len(content) / (1024 * 1024)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)
            
        gc.collect()
        
        try:
            processor = LogProcessor(temp_path, tail_lines=tail_size)
            
            # Tail should be fast regardless of file size
            start_time = time.time()
            with processor:
                tail_lines = list(processor.read_lines())
            end_time = time.time()
            
            processing_time = end_time - start_time
            
            # Verify correctness
            assert len(tail_lines) == tail_size
            
            # Tail should be fast regardless of file size (max 5 seconds)
            assert processing_time < 5.0, (
                f"Tailing {tail_size} lines from {file_size_mb:.1f}MB file took "
                f"{processing_time:.2f}s, expected <5.0s"
            )
            
            # Verify we got the last lines
            assert f"entry number {file_size_lines - 1}" in tail_lines[-1].content
            
            print(f"\nTailed {tail_size} lines from {file_size_mb:.1f}MB file in {processing_time:.2f}s")
            
        finally:
            temp_path.unlink()
            gc.collect()
    
    def test_memory_efficiency_large_file(self):
        """Test that very large files don't consume excessive memory."""
        try:
            import psutil
            import os
        except ImportError:
            pytest.skip("psutil not available for memory testing")
        
        process = psutil.Process(os.getpid())
        
        # Generate a 50MB+ file (approximately 500K lines)
        line_count = 500000
        content = self.generate_large_log_content(line_count, include_variety=False)
        file_size_mb = len(content) / (1024 * 1024)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)
        
        # Get baseline memory
        gc.collect()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        try:
            processor = LogProcessor(temp_path)
            
            # Process file in chunks to test streaming behavior
            with processor:
                lines_processed = 0
                for line in processor.read_lines():
                    lines_processed += 1
                    
                    # Check memory every 50K lines
                    if lines_processed % 50000 == 0:
                        current_memory = process.memory_info().rss / 1024 / 1024
                        memory_increase = current_memory - initial_memory
                        
                        # Memory increase should be reasonable (<200MB for 50MB file)
                        assert memory_increase < 200, (
                            f"Memory increased by {memory_increase:.1f}MB after processing "
                            f"{lines_processed} lines from {file_size_mb:.1f}MB file"
                        )
            
            final_memory = process.memory_info().rss / 1024 / 1024
            total_memory_increase = final_memory - initial_memory
            
            print(f"\nProcessed {file_size_mb:.1f}MB file with {total_memory_increase:.1f}MB memory increase")
            
            # Total memory increase should be much smaller than file size
            assert total_memory_increase < file_size_mb * 0.5, (
                f"Memory increase ({total_memory_increase:.1f}MB) should be less than "
                f"50% of file size ({file_size_mb:.1f}MB)"
            )
            
        finally:
            temp_path.unlink()
            gc.collect()
    
    def test_streaming_behavior_verification(self):
        """Verify that large files are processed in streaming fashion, not loaded entirely."""
        try:
            import psutil
            import os
        except ImportError:
            pytest.skip("psutil not available for memory testing")
        
        # Create a very large file (100K lines)
        line_count = 100000
        content = self.generate_large_log_content(line_count, include_variety=False)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(content) 
            temp_path = Path(f.name)
            
        file_size_mb = temp_path.stat().st_size / (1024 * 1024)
        
        process = psutil.Process(os.getpid())
        gc.collect()
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        try:
            processor = LogProcessor(temp_path)
            
            with processor:
                line_iterator = processor.read_lines()
                
                # Process first 100 lines
                first_batch = []
                for i, line in enumerate(line_iterator):
                    first_batch.append(line)
                    if i >= 99:  # 100 lines
                        break
                
                # Check memory after processing only 100 lines
                early_memory = process.memory_info().rss / 1024 / 1024
                early_increase = early_memory - initial_memory
                
                # Should not have loaded entire file into memory
                assert early_increase < file_size_mb * 0.1, (
                    f"After processing 100 lines, memory increased by {early_increase:.1f}MB, "
                    f"which suggests entire {file_size_mb:.1f}MB file was loaded"
                )
                
                # Process remaining lines in batches to verify streaming
                remaining_count = 0
                for line in line_iterator:
                    remaining_count += 1
                
                assert len(first_batch) == 100
                assert remaining_count == line_count - 100
                
                print(f"\nVerified streaming behavior: processed {file_size_mb:.1f}MB file "
                      f"with only {early_increase:.1f}MB early memory increase")
                
        finally:
            temp_path.unlink()
            gc.collect()
    
    def test_large_file_with_complex_processing(self):
        """Test large files with full processing pipeline (exclusions + styling)."""
        line_count = 50000  # 50K lines for complex processing test
        
        # Generate content with variety for exclusion testing
        content = self.generate_large_log_content(line_count, include_variety=True)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)
            
        gc.collect()
        
        try:
            # Set up full processing pipeline
            processor = LogProcessor(temp_path)
            exclusion_manager = ExclusionManager(
                patterns=["DEBUG", "TRACE"],  # Exclude debug/trace logs
                is_regex=False,
                case_sensitive=False
            )
            config = get_default_config()
            styling_engine = StylingEngine(config.styling)
            
            start_time = time.time()
            
            # Full pipeline processing
            with processor:
                raw_lines = list(processor.read_lines())
            
            # Apply exclusions
            filtered_lines = exclusion_manager.filter_lines([line.content for line in raw_lines])
            
            # Apply styling to filtered lines  
            styled_lines = []
            for line in filtered_lines:
                styled = styling_engine.apply_styling(line)
                styled_lines.append(styled)
                
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Verify results
            assert len(raw_lines) == line_count
            excluded_count = exclusion_manager.get_excluded_count()
            assert len(filtered_lines) == line_count - excluded_count
            assert len(styled_lines) == len(filtered_lines)
            
            # Should complete complex processing in reasonable time (<30s for 50K lines)
            assert processing_time < 30.0, (
                f"Complex processing of {line_count} lines took {processing_time:.2f}s, expected <30s"
            )
            
            # Verify exclusions worked
            assert excluded_count > 0, "Should have excluded some DEBUG/TRACE lines"
            for line in filtered_lines:
                assert "DEBUG" not in line and "TRACE" not in line
                
            # Verify styling applied
            for styled_line in styled_lines:
                assert hasattr(styled_line, 'plain')
                
            print(f"\nComplex processing: {line_count} lines -> {len(filtered_lines)} filtered "
                  f"({excluded_count} excluded) -> {len(styled_lines)} styled in {processing_time:.2f}s")
                  
        finally:
            temp_path.unlink()
            gc.collect()
    
    def test_very_long_lines_handling(self):
        """Test handling of files with very long lines (log entries)."""
        # Create file with mix of normal and very long lines
        lines = []
        
        # Normal lines
        for i in range(1000):
            lines.append(f"2024-01-15 10:30:{i:02d} INFO Normal log entry {i}")
            
        # Very long lines (simulating stack traces, JSON payloads, etc.)
        long_content = "A" * 10000  # 10KB line
        for i in range(100):
            lines.append(f"2024-01-15 10:31:{i:02d} ERROR Exception occurred: {long_content} (entry {i})")
            
        # More normal lines
        for i in range(1000):
            lines.append(f"2024-01-15 10:32:{i:02d} INFO Recovery attempt {i}")
            
        content = "\n".join(lines)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)
            
        try:
            processor = LogProcessor(temp_path)
            
            start_time = time.time()
            with processor:
                processed_lines = list(processor.read_lines())
            end_time = time.time()
            
            processing_time = end_time - start_time
            
            # Verify all lines processed
            assert len(processed_lines) == 2100  # 1000 + 100 + 1000
            
            # Should handle long lines efficiently
            assert processing_time < 10.0, f"Processing very long lines took {processing_time:.2f}s, expected <10s"
            
            # Verify long lines are intact
            long_lines = [line for line in processed_lines if "Exception occurred" in line.content]
            assert len(long_lines) == 100
            
            for long_line in long_lines:
                assert len(long_line.content) > 10000  # Should contain the long content
                
        finally:
            temp_path.unlink()
    
    def test_encoding_handling_large_file(self):
        """Test handling of large files with mixed encoding issues."""
        # Create content with some encoding challenges
        lines = []
        
        # Normal ASCII content
        for i in range(10000):
            lines.append(f"2024-01-15 10:30:{i:02d} INFO Processing request {i}")
            
        # Unicode content
        unicode_chars = ["🚨", "❌", "✅", "⚠️", "🔄", "📊"]
        for i in range(1000):
            char = unicode_chars[i % len(unicode_chars)]
            lines.append(f"2024-01-15 10:31:{i:02d} INFO Status update {char} for operation {i}")
            
        # Mixed language content  
        for i in range(1000):
            lines.append(f"2024-01-15 10:32:{i:02d} INFO Tëst mëssagë {i} with spëcial charactërs")
            
        content = "\n".join(lines)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = Path(f.name)
            
        try:
            processor = LogProcessor(temp_path)
            
            with processor:
                processed_lines = list(processor.read_lines())
                
            # Should handle all lines properly
            assert len(processed_lines) == 12000  # 10000 + 1000 + 1000
            
            # Verify Unicode content is preserved
            unicode_lines = [line for line in processed_lines if any(char in line.content for char in unicode_chars)]
            assert len(unicode_lines) == 1000
            
            # Verify special characters are preserved
            special_lines = [line for line in processed_lines if "spëcial charactërs" in line.content]
            assert len(special_lines) == 1000
            
        finally:
            temp_path.unlink()


@pytest.mark.slow  
class TestProductionScaleStressTests:
    """
    Stress tests for production scenarios and edge cases.
    
    These test extreme scenarios that might occur in production environments.
    """
    
    def test_rapid_file_modification_during_processing(self):
        """Test behavior when file is rapidly modified during processing."""
        # Create initial content
        initial_lines = 10000
        content = "\n".join([
            f"2024-01-15 10:30:{i:02d} INFO Initial entry {i}"
            for i in range(initial_lines)
        ])
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)
            
        try:
            processor = LogProcessor(temp_path)
            
            # Start processing
            with processor:
                lines_read = 0
                for line in processor.read_lines():
                    lines_read += 1
                    
                    # Modify file partway through reading
                    if lines_read == 5000:
                        # Append more content
                        with open(temp_path, 'a') as append_file:
                            for i in range(initial_lines, initial_lines + 1000):
                                append_file.write(f"\n2024-01-15 10:31:{i:02d} INFO Appended entry {i}")
                    
                    # Don't process indefinitely
                    if lines_read >= initial_lines + 500:  # Stop before reading all appended content
                        break
                        
            # Should handle gracefully without crashing
            assert lines_read >= initial_lines  # Should read at least initial content
            
        finally:
            temp_path.unlink()
    
    def test_memory_pressure_handling(self):
        """Test behavior under memory pressure with multiple large files."""
        try:
            import psutil
            import os
        except ImportError:
            pytest.skip("psutil not available for memory testing")
            
        # Create multiple moderately large files
        file_count = 3
        lines_per_file = 20000
        temp_files = []
        
        # Generate files
        for file_idx in range(file_count):
            content = "\n".join([
                f"2024-01-15 10:30:{i:02d} INFO File {file_idx} entry {i}" 
                for i in range(lines_per_file)
            ])
            
            with tempfile.NamedTemporaryFile(mode='w', suffix=f'_{file_idx}.log', delete=False) as f:
                f.write(content)
                temp_files.append(Path(f.name))
                
        process = psutil.Process(os.getpid())
        gc.collect()
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        try:
            processors = []
            all_lines = []
            
            # Process all files simultaneously
            for temp_file in temp_files:
                processor = LogProcessor(temp_file)
                processors.append(processor)
                
                with processor:
                    file_lines = list(processor.read_lines())
                    all_lines.append(file_lines)
                    
            # Check final memory usage
            final_memory = process.memory_info().rss / 1024 / 1024
            memory_increase = final_memory - initial_memory
            
            # Verify processing correctness
            assert len(all_lines) == file_count
            for file_lines in all_lines:
                assert len(file_lines) == lines_per_file
                
            # Memory increase should be reasonable
            expected_max_memory = file_count * 50  # Max 50MB per file
            assert memory_increase < expected_max_memory, (
                f"Memory increased by {memory_increase:.1f}MB for {file_count} files, "
                f"expected <{expected_max_memory}MB"
            )
            
            print(f"\nProcessed {file_count} files with {memory_increase:.1f}MB memory increase")
                
        finally:
            for temp_file in temp_files:
                temp_file.unlink()
            gc.collect()
    
    def test_performance_degradation_analysis(self):
        """Analyze performance scaling to detect degradation patterns."""
        test_sizes = [1000, 5000, 10000, 25000, 50000]
        performance_results = []
        
        for size in test_sizes:
            content = "\n".join([
                f"2024-01-15 10:30:{i:02d} INFO Performance test entry {i}"
                for i in range(size)
            ])
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
                f.write(content)
                temp_path = Path(f.name)
                
            try:
                processor = LogProcessor(temp_path)
                
                # Measure processing time
                start_time = time.time()
                with processor:
                    lines = list(processor.read_lines())
                end_time = time.time()
                
                processing_time = end_time - start_time
                lines_per_second = size / processing_time
                
                performance_results.append({
                    'size': size,
                    'time': processing_time,
                    'lines_per_second': lines_per_second
                })
                
                assert len(lines) == size
                
            finally:
                temp_path.unlink()
                gc.collect()
        
        # Analyze performance scaling
        print("\nPerformance Scaling Analysis:")
        for result in performance_results:
            print(f"  {result['size']:5d} lines: {result['time']:.3f}s ({result['lines_per_second']:.0f} lines/sec)")
            
        # Performance should not degrade drastically
        # Check that largest file processes at reasonable speed
        largest_result = performance_results[-1]
        assert largest_result['lines_per_second'] > 1000, (
            f"Large file processing too slow: {largest_result['lines_per_second']:.0f} lines/sec, expected >1000"
        )
        
        # Check that performance scaling is roughly linear (not exponential degradation)
        small_lps = performance_results[0]['lines_per_second']  # lines per second for smallest
        large_lps = performance_results[-1]['lines_per_second']  # lines per second for largest
        
        # Large files should process at least 25% the speed of small files
        assert large_lps > small_lps * 0.25, (
            f"Performance degradation too severe: {large_lps:.0f} vs {small_lps:.0f} lines/sec"
        ) 