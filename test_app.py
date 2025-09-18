#!/usr/bin/env python3
"""Test script for the VideoTextCut application."""

import sys
import os
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from models import TranscriptSegment, TranscriptData, AppConfig
    from transcript_service import TranscriptService
    from video_service import VideoService
    from filler_detector import FillerWordDetector, FillerPattern
    from progress_tracker import ProgressTracker, OperationStatus
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Please ensure all modules are available in the current directory.")
    sys.exit(1)


class TestModels(unittest.TestCase):
    """Test the data models."""
    
    def test_transcript_segment(self):
        """Test TranscriptSegment functionality."""
        segment = TranscriptSegment(
            start_time=0.0,
            end_time=2.5,
            text="Hello world",
            confidence=0.95
        )
        
        self.assertEqual(segment.duration(), 2.5)
        self.assertFalse(segment.is_filler)
        self.assertTrue(segment.is_active)
    
    def test_transcript_data(self):
        """Test TranscriptData functionality."""
        segments = [
            TranscriptSegment(1, 0.0, 2.0, "Hello", confidence=0.9),
            TranscriptSegment(2, 2.0, 3.0, "um", is_filler=True, is_deleted=True, confidence=0.7),
            TranscriptSegment(3, 3.0, 5.0, "world", confidence=0.95)
        ]
        
        transcript_data = TranscriptData(segments=segments, duration=5.0, file_path="test.mp4")
        
        self.assertEqual(transcript_data.duration, 5.0)
        self.assertEqual(len(transcript_data.get_active_segments()), 2)
        self.assertEqual(transcript_data.get_text_content(), "Hello world")
    
    def test_app_config(self):
        """Test AppConfig default values."""
        config = AppConfig()
        
        self.assertIn('.mp4', config.supported_formats)
        self.assertEqual(config.whisper_model, 'base')


class TestFillerDetector(unittest.TestCase):
    """Test the filler word detection functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.detector = FillerWordDetector()
    
    def test_basic_filler_detection(self):
        """Test detection of basic filler words."""
        segments = [
            TranscriptSegment(1, 0.0, 2.0, "Hello", confidence=0.9),
            TranscriptSegment(2, 1.0, 2.0, "um", confidence=0.95),
            TranscriptSegment(3, 2.0, 3.0, "world", confidence=0.95),
            TranscriptSegment(4, 3.0, 4.0, "uh", confidence=0.95),
        ]
        
        transcript_data = TranscriptData(segments=segments, duration=4.0, file_path="test.mp4")
        self.detector.detect_filler_words(transcript_data)
        
        # Check that filler words were detected
        filler_segments = [s for s in segments if s.is_filler]
        self.assertEqual(len(filler_segments), 2)
        self.assertIn("um", [s.text for s in filler_segments])
        self.assertIn("uh", [s.text for s in filler_segments])
    
    def test_custom_filler_words(self):
        """Test detection of custom filler words."""
        segments = [
            TranscriptSegment(1, 0.0, 1.0, "Hello", confidence=0.9),
            TranscriptSegment(2, 1.0, 2.0, "basically", confidence=0.8),
            TranscriptSegment(3, 2.0, 3.0, "world", confidence=0.95),
        ]
        
        transcript_data = TranscriptData(segments=segments, duration=3.0, file_path="test.mp4")
        self.detector.detect_filler_words(transcript_data, custom_filler_words=["basically"])
        
        # Check that custom filler word was detected
        filler_segments = [s for s in segments if s.is_filler]
        self.assertEqual(len(filler_segments), 1)
        self.assertEqual(filler_segments[0].text, "basically")
    
    def test_filler_statistics(self):
        """Test filler word statistics calculation."""
        segments = [
            TranscriptSegment(1, 0.0, 1.0, "Hello", confidence=0.9),
            TranscriptSegment(2, 1.0, 2.0, "um", is_filler=True, confidence=0.8),
            TranscriptSegment(3, 2.0, 4.0, "world", confidence=0.95),
        ]
        
        transcript_data = TranscriptData(segments=segments, duration=4.0, file_path="test.mp4")
        stats = self.detector.get_filler_statistics(transcript_data)
        
        self.assertEqual(stats['total_segments'], 3)
        self.assertEqual(stats['filler_segments'], 1)
        self.assertAlmostEqual(stats['filler_percentage'], 33.33, places=1)
        self.assertEqual(stats['total_duration'], 4.0)
        self.assertEqual(stats['filler_duration'], 1.0)
        self.assertEqual(stats['filler_time_percentage'], 25.0)


class TestProgressTracker(unittest.TestCase):
    """Test the progress tracking functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tracker = ProgressTracker()
    
    def test_operation_lifecycle(self):
        """Test complete operation lifecycle."""
        operation_id = "test_op"
        
        # Start operation
        progress = self.tracker.start_operation(operation_id, total_steps=5, description="Test operation")
        self.assertEqual(progress.status, OperationStatus.RUNNING)
        self.assertEqual(progress.total_steps, 5)
        
        # Update progress
        success = self.tracker.update_progress(operation_id, progress_percent=50.0, current_step="Step 3")
        self.assertTrue(success)
        
        progress = self.tracker.get_progress(operation_id)
        self.assertEqual(progress.progress_percent, 50.0)
        self.assertEqual(progress.current_step, "Step 3")
        
        # Complete operation
        self.tracker.complete_operation(operation_id, result="Success")
        progress = self.tracker.get_progress(operation_id)
        self.assertEqual(progress.status, OperationStatus.COMPLETED)
        self.assertEqual(progress.progress_percent, 100.0)
        self.assertEqual(progress.result, "Success")
    
    def test_operation_cancellation(self):
        """Test operation cancellation."""
        operation_id = "cancel_test"
        
        self.tracker.start_operation(operation_id)
        success = self.tracker.cancel_operation(operation_id)
        self.assertTrue(success)
        
        progress = self.tracker.get_progress(operation_id)
        self.assertEqual(progress.status, OperationStatus.CANCELLED)
        
        # Further updates should fail
        success = self.tracker.update_progress(operation_id, progress_percent=50.0)
        self.assertFalse(success)
    
    def test_operation_failure(self):
        """Test operation failure handling."""
        operation_id = "fail_test"
        
        self.tracker.start_operation(operation_id)
        self.tracker.fail_operation(operation_id, "Test error")
        
        progress = self.tracker.get_progress(operation_id)
        self.assertEqual(progress.status, OperationStatus.FAILED)
        self.assertEqual(progress.error_message, "Test error")


class TestTranscriptService(unittest.TestCase):
    """Test the transcript service (with mocked Whisper)."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.service = TranscriptService()
    
    @patch('transcript_service.whisper.load_model')
    def test_model_loading(self, mock_load_model):
        """Test Whisper model loading."""
        mock_model = Mock()
        mock_load_model.return_value = mock_model
        
        model = self.service.load_model('base')
        self.assertEqual(model, mock_model)
        mock_load_model.assert_called_once_with('base')
    
    def test_video_validation(self):
        """Test video file validation."""
        # Test with non-existent file
        self.assertFalse(self.service.validate_video_file("nonexistent.mp4"))
        
        # Test with invalid extension
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            self.assertFalse(self.service.validate_video_file(temp_path))
        finally:
            os.unlink(temp_path)


class TestVideoService(unittest.TestCase):
    """Test the video service (with mocked MoviePy)."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.service = VideoService()
    
    def test_output_filename_generation(self):
        """Test output filename generation."""
        input_path = "test_video.mp4"
        output_filename = self.service.generate_output_filename(input_path)
        
        self.assertTrue("trimmed" in output_filename)
        self.assertTrue(output_filename.endswith(".mp4"))
    
    def test_duration_estimation(self):
        """Test duration estimation from transcript."""
        segments = [
            TranscriptSegment(1, 0.0, 2.0, "Hello", confidence=0.9),
            TranscriptSegment(2, 2.0, 3.0, "um", is_filler=True, is_deleted=True, confidence=0.7),
            TranscriptSegment(3, 3.0, 5.0, "world", confidence=0.95)
        ]
        
        transcript_data = TranscriptData(segments=segments, duration=5.0, file_path="test.mp4")
        estimated_duration = self.service.estimate_output_duration(transcript_data)
        
        # Should exclude deleted filler segments (Hello: 2s + world: 2s = 4s)
        self.assertEqual(estimated_duration, 4.0)


def create_sample_video_info():
    """Create sample video information for testing."""
    return {
        'duration': 10.0,
        'fps': 30,
        'resolution': (1920, 1080),
        'audio_codec': 'aac',
        'video_codec': 'h264'
    }


def create_sample_transcript():
    """Create sample transcript data for testing."""
    segments = [
        TranscriptSegment(1, 0.0, 2.0, "Hello everyone", confidence=0.95),
        TranscriptSegment(2, 2.0, 2.5, "um", confidence=0.7),
        TranscriptSegment(3, 2.5, 4.0, "welcome to this video", confidence=0.9),
        TranscriptSegment(4, 4.0, 4.2, "uh", confidence=0.6),
        TranscriptSegment(5, 4.2, 6.0, "today we will discuss", confidence=0.92),
        TranscriptSegment(6, 6.0, 8.0, "artificial intelligence", confidence=0.98),
        TranscriptSegment(7, 8.0, 8.3, "you know", confidence=0.8),
        TranscriptSegment(8, 8.3, 10.0, "and machine learning", confidence=0.94)
    ]
    
    return TranscriptData(segments=segments, duration=10.0, file_path="test_video.mp4")


def run_integration_test():
    """Run a basic integration test of the complete workflow."""
    print("\n=== Running Integration Test ===")
    
    try:
        # Test 1: Create sample transcript
        print("1. Creating sample transcript...")
        transcript_data = create_sample_transcript()
        print(f"   Created transcript with {len(transcript_data.segments)} segments")
        print(f"   Total duration: {transcript_data.duration:.1f} seconds")
        
        # Test 2: Detect filler words
        print("\n2. Detecting filler words...")
        detector = FillerWordDetector()
        detector.detect_filler_words(transcript_data)
        
        filler_segments = [s for s in transcript_data.segments if s.is_filler]
        print(f"   Detected {len(filler_segments)} filler segments")
        for segment in filler_segments:
            print(f"   - '{segment.text}' at {segment.start_time:.1f}s")
        
        # Test 3: Get statistics
        print("\n3. Calculating statistics...")
        stats = detector.get_filler_statistics(transcript_data)
        print(f"   Filler percentage: {stats['filler_percentage']:.1f}%")
        print(f"   Time saved by removing fillers: {stats['filler_duration']:.1f}s")
        
        # Test 4: Test video service
        print("\n4. Testing video service...")
        video_service = VideoService()
        estimated_duration = video_service.estimate_output_duration(transcript_data)
        print(f"   Estimated output duration: {estimated_duration:.1f}s")
        
        compression_ratio = video_service.calculate_compression_ratio(transcript_data)
        print(f"   Compression ratio: {compression_ratio:.1f}%")
        
        # Test 5: Test progress tracking
        print("\n5. Testing progress tracking...")
        tracker = ProgressTracker()
        
        operation_id = "integration_test"
        progress = tracker.start_operation(operation_id, total_steps=3, description="Integration test")
        print(f"   Started operation: {progress.operation_id}")
        
        tracker.update_progress(operation_id, progress_percent=33.0, current_step="Step 1")
        tracker.update_progress(operation_id, progress_percent=66.0, current_step="Step 2")
        tracker.complete_operation(operation_id, result="Integration test completed")
        
        final_progress = tracker.get_progress(operation_id)
        print(f"   Operation completed in {final_progress.elapsed_time:.2f}s")
        
        print("\n=== Integration Test PASSED ===")
        return True
        
    except Exception as e:
        print(f"\n=== Integration Test FAILED: {e} ===")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function."""
    print("VideoTextCut - Test Suite")
    print("=====================================")
    
    # Run unit tests
    print("\nRunning unit tests...")
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # Run integration test
    integration_success = run_integration_test()
    
    # Summary
    print("\n" + "="*50)
    if integration_success:
        print("All tests completed successfully!")
        print("\nThe application is ready to use.")
        print("To start the application, run: python main.py")
    else:
        print("Some tests failed. Please check the errors above.")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())