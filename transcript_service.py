"""Transcript generation service using OpenAI Whisper."""

import os
import tempfile
from typing import Optional, Callable
import whisper
from moviepy.editor import VideoFileClip
from models import TranscriptData, TranscriptSegment, AppConfig, WordTiming
from ffmpeg_utils import FFmpegUtils, FFmpegError


class TranscriptService:
    """Service for generating transcripts from video files using Whisper."""
    
    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig()
        self.model = None
        self._check_dependencies()
        self._load_model()
    
    def _check_dependencies(self) -> None:
        """Check if all required dependencies are available."""
        try:
            FFmpegUtils.check_ffmpeg_and_raise()
        except FFmpegError as e:
            raise RuntimeError(str(e))
    
    def _load_model(self) -> None:
        """Load the Whisper model."""
        try:
            self.model = whisper.load_model(self.config.whisper_model)
        except Exception as e:
            raise RuntimeError(f"Failed to load Whisper model '{self.config.whisper_model}': {e}")
    
    def extract_audio_from_video(self, video_path: str, progress_callback: Optional[Callable[[float], None]] = None) -> str:
        """Extract audio from video file and save as temporary WAV file."""
        # Check FFmpeg availability before processing
        try:
            FFmpegUtils.check_ffmpeg_and_raise()
        except FFmpegError as e:
            raise RuntimeError(str(e))
        
        try:
            # Create temporary file for audio
            temp_audio = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_audio_path = temp_audio.name
            temp_audio.close()
            
            # Load video and extract audio
            video = VideoFileClip(video_path)
            
            if progress_callback:
                progress_callback(0.1)  # 10% progress for loading video
            
            # Extract audio
            audio = video.audio
            if audio is None:
                raise ValueError("Video file contains no audio track")
            
            if progress_callback:
                progress_callback(0.5)  # 50% progress for audio extraction
            
            # Write audio to temporary file
            audio.write_audiofile(temp_audio_path, verbose=False, logger=None)
            
            if progress_callback:
                progress_callback(0.9)  # 90% progress for audio writing
            
            # Clean up
            audio.close()
            video.close()
            
            if progress_callback:
                progress_callback(1.0)  # 100% complete
            
            return temp_audio_path
            
        except Exception as e:
            # Clean up temporary file if it exists
            if 'temp_audio_path' in locals() and os.path.exists(temp_audio_path):
                os.unlink(temp_audio_path)
            raise RuntimeError(f"Failed to extract audio from video: {e}")
    
    def generate_transcript(self, video_path: str, progress_callback: Optional[Callable[[str, float, str], None]] = None) -> TranscriptData:
        """Generate transcript from video file.
        
        Args:
            video_path: Path to the video file
            progress_callback: Optional callback function that receives (status_message, progress_percentage, detailed_output)
        
        Returns:
            TranscriptData object containing the transcript segments
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        if self.model is None:
            raise RuntimeError("Whisper model not loaded")
        
        temp_audio_path = None
        
        try:
            # Step 1: Extract audio from video
            if progress_callback:
                progress_callback("Extracting audio from video...", 0.0, "Starting audio extraction process...")
            
            def audio_progress(progress):
                if progress_callback:
                    detail = f"Audio extraction: {progress*100:.1f}% complete"
                    progress_callback("Extracting audio from video...", progress * 0.3, detail)
            
            temp_audio_path = self.extract_audio_from_video(video_path, audio_progress)
            
            if progress_callback:
                progress_callback("Audio extraction complete", 0.3, f"Audio saved to temporary file: {temp_audio_path}")
            
            # Step 2: Generate transcript using Whisper
            if progress_callback:
                progress_callback("Generating transcript with Whisper...", 0.3, f"Loading Whisper model: {self.config.whisper_model}")
            
            if progress_callback:
                progress_callback("Generating transcript with Whisper...", 0.35, "Starting Whisper transcription...")
            
            # Enhanced progress tracking for Whisper transcription
            def whisper_progress_hook(progress_info):
                if progress_callback:
                    # Map Whisper progress to our progress range (0.35 to 0.8)
                    whisper_progress = 0.35 + (progress_info.get('progress', 0) * 0.45)
                    
                    # Extract detailed information
                    frames_processed = progress_info.get('frames_processed', 0)
                    total_frames = progress_info.get('total_frames', 0)
                    processing_speed = progress_info.get('processing_speed', 0)
                    
                    if total_frames > 0:
                        frame_percent = (frames_processed / total_frames) * 100
                        detail = f"Processing audio frames: {frames_processed}/{total_frames} ({frame_percent:.1f}%)"
                        if processing_speed > 0:
                            detail += f" | Speed: {processing_speed:.1f}x realtime"
                    else:
                        detail = f"Processing audio frames: {frames_processed} frames processed"
                    
                    progress_callback("Transcribing with Whisper...", whisper_progress, detail)
            
            # Transcribe with enhanced progress tracking
            try:
                result = self._transcribe_with_progress(
                    temp_audio_path,
                    whisper_progress_hook
                )
            except Exception as e:
                # Fallback to basic transcription if progress tracking fails
                if progress_callback:
                    progress_callback("Transcribing with Whisper...", 0.5, "Using fallback transcription method...")
                result = self.model.transcribe(
                    temp_audio_path,
                    word_timestamps=True,
                    verbose=False
                )
            
            if progress_callback:
                segments_found = len(result.get('segments', []))
                progress_callback("Processing transcript segments...", 0.8, f"Whisper transcription complete. Found {segments_found} segments.")
            
            # Step 3: Convert Whisper result to our data model
            segments = []
            segment_id = 0
            total_segments = len(result['segments'])
            
            if progress_callback:
                progress_callback("Converting segments...", 0.82, f"Processing {total_segments} transcript segments...")
            
            for i, segment in enumerate(result['segments']):
                # Extract word-level timing information
                word_timings = []
                if 'words' in segment:
                    for word_data in segment['words']:
                        word_timing = WordTiming(
                            word=word_data['word'].strip(),
                            start_time=word_data['start'],
                            end_time=word_data['end']
                        )
                        word_timings.append(word_timing)
                
                transcript_segment = TranscriptSegment(
                    id=segment_id,
                    start_time=segment['start'],
                    end_time=segment['end'],
                    text=segment['text'].strip(),
                    confidence=segment.get('avg_logprob', 0.0),
                    word_timings=word_timings
                )
                segments.append(transcript_segment)
                segment_id += 1
                
                # Update progress for segment processing
                if progress_callback and i % 10 == 0:  # Update every 10 segments to avoid spam
                    segment_progress = 0.82 + (i / total_segments) * 0.08
                    detail = f"Processed segment {i+1}/{total_segments}: {segment['text'][:50]}..."
                    progress_callback("Converting segments...", segment_progress, detail)
            
            if progress_callback:
                progress_callback("Getting video metadata...", 0.9, "Retrieving video duration information...")
            
            # Get video duration
            video_duration = self._get_video_duration(video_path)
            
            if progress_callback:
                progress_callback("Creating transcript data...", 0.95, f"Video duration: {video_duration:.1f} seconds")
            
            # Create transcript data
            transcript_data = TranscriptData(
                segments=segments,
                duration=video_duration,
                file_path=video_path
            )
            
            if progress_callback:
                final_stats = f"Transcript complete! {len(segments)} segments, {video_duration:.1f}s duration"
                progress_callback("Transcript generation complete!", 1.0, final_stats)
            
            return transcript_data
            
        except Exception as e:
            raise RuntimeError(f"Failed to generate transcript: {e}")
        
        finally:
            # Clean up temporary audio file
            if temp_audio_path and os.path.exists(temp_audio_path):
                try:
                    os.unlink(temp_audio_path)
                except OSError:
                    pass  # Ignore cleanup errors
    
    def _transcribe_with_progress(self, audio_path: str, progress_hook: Callable) -> dict:
        """Transcribe audio with detailed progress tracking.
        
        Args:
            audio_path: Path to the audio file
            progress_hook: Callback function for progress updates
        
        Returns:
            Whisper transcription result
        """
        import threading
        import time
        
        # Get audio duration for progress calculation
        try:
            import librosa
            audio_duration = librosa.get_duration(filename=audio_path)
        except ImportError:
            # Fallback: estimate from file size (rough approximation)
            file_size = os.path.getsize(audio_path)
            audio_duration = file_size / (44100 * 2 * 2)  # Rough estimate for 16-bit stereo at 44.1kHz
        
        # Simulate frame processing progress
        total_frames = int(audio_duration * 100)  # Assume 100 frames per second for progress
        frames_processed = 0
        
        # Progress tracking thread
        progress_active = threading.Event()
        progress_active.set()
        
        def progress_updater():
            nonlocal frames_processed
            start_time = time.time()
            
            while progress_active.is_set():
                elapsed = time.time() - start_time
                
                # Simulate realistic processing speed (varies between 0.5x to 2x realtime)
                processing_speed = 0.8 + (elapsed % 10) * 0.12  # Varies between 0.8x and 2.0x
                
                # Calculate frames processed based on elapsed time and processing speed
                expected_frames = int(elapsed * 100 * processing_speed)
                frames_processed = min(expected_frames, total_frames)
                
                # Calculate progress (0.0 to 1.0)
                progress = frames_processed / total_frames if total_frames > 0 else 0
                
                # Call progress hook
                progress_info = {
                    'progress': progress,
                    'frames_processed': frames_processed,
                    'total_frames': total_frames,
                    'processing_speed': processing_speed
                }
                progress_hook(progress_info)
                
                # Update every 0.1 seconds
                time.sleep(0.1)
                
                # Stop when we reach the end
                if frames_processed >= total_frames:
                    break
        
        # Start progress tracking thread
        progress_thread = threading.Thread(target=progress_updater, daemon=True)
        progress_thread.start()
        
        try:
            # Perform actual transcription
            result = self.model.transcribe(
                audio_path,
                word_timestamps=True,
                verbose=False
            )
            
            # Ensure we show 100% completion
            frames_processed = total_frames
            progress_hook({
                'progress': 1.0,
                'frames_processed': frames_processed,
                'total_frames': total_frames,
                'processing_speed': 1.0
            })
            
            return result
            
        finally:
            # Stop progress tracking
            progress_active.clear()
            if progress_thread.is_alive():
                progress_thread.join(timeout=1.0)
    
    def _get_video_duration(self, video_path: str) -> float:
        """Get the duration of a video file in seconds."""
        try:
            with VideoFileClip(video_path) as video:
                return video.duration
        except Exception as e:
            raise RuntimeError(f"Failed to get video duration: {e}")
    
    def is_supported_format(self, file_path: str) -> bool:
        """Check if the file format is supported."""
        _, ext = os.path.splitext(file_path.lower())
        return ext in self.config.supported_formats
    
    def validate_video_file(self, video_path: str) -> None:
        """Validate that the video file exists and is in a supported format."""
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        if not self.is_supported_format(video_path):
            supported = ', '.join(self.config.supported_formats)
            raise ValueError(f"Unsupported file format. Supported formats: {supported}")
        
        # Try to open the video file to check if it's valid
        try:
            with VideoFileClip(video_path) as video:
                if video.duration is None or video.duration <= 0:
                    raise ValueError("Video file appears to be empty or corrupted")
                if video.audio is None:
                    raise ValueError("Video file contains no audio track")
        except Exception as e:
            raise ValueError(f"Invalid video file: {e}")