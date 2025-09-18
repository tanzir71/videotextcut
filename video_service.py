"""Video processing service using MoviePy for trimming and editing."""

import os
import tempfile
from typing import List, Tuple, Optional, Callable
from moviepy.editor import VideoFileClip, concatenate_videoclips
from models import TranscriptData, TranscriptSegment, AppConfig


class VideoService:
    """Service for processing video files based on transcript data."""
    
    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig()
    
    def trim_video_by_transcript(self, 
                               video_path: str, 
                               transcript_data: TranscriptData, 
                               output_path: str,
                               progress_callback: Optional[Callable[[str, float, Optional[str]], None]] = None) -> str:
        """Trim video based on transcript segments with word-level precision.
        
        Args:
            video_path: Path to the input video file
            transcript_data: TranscriptData containing segments to keep
            output_path: Path for the output video file
            progress_callback: Optional callback for progress updates
        
        Returns:
            Path to the trimmed video file
        """
        if progress_callback:
            progress_callback("Starting video trimming...", 0.0)
        
        # Validate inputs
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        self.validate_output_path(output_path)
        
        try:
            if progress_callback:
                progress_callback("Loading video file...", 0.1)
            
            # Load the video
            video = VideoFileClip(video_path)
            
            if progress_callback:
                progress_callback("Analyzing transcript for active time ranges...", 0.2)
            
            # Get active time ranges (word-level precision)
            active_ranges = transcript_data.get_active_time_ranges()
            
            if not active_ranges:
                raise ValueError("No active time ranges found in transcript")
            
            if progress_callback:
                progress_callback(f"Creating {len(active_ranges)} video clips from time ranges...", 0.3)
            
            # Create clips for each active time range
            clips = []
            total_ranges = len(active_ranges)
            
            for i, (start_time, end_time) in enumerate(active_ranges):
                try:
                    # Ensure valid time range
                    start_time = max(0, start_time)
                    end_time = min(video.duration, end_time)
                    
                    if end_time > start_time:
                        # Create subclip for this time range
                        clip = video.subclip(start_time, end_time)
                        clips.append(clip)
                    
                    if progress_callback:
                        range_progress = 0.3 + (0.4 * (i + 1) / total_ranges)
                        progress_callback(f"Processing time range {i + 1}/{total_ranges} ({start_time:.1f}s - {end_time:.1f}s)...", range_progress)
                        
                except Exception as e:
                    print(f"Warning: Could not create clip for time range {start_time:.1f}s - {end_time:.1f}s: {e}")
                    continue
            
            if not clips:
                raise ValueError("No valid video clips could be created from active time ranges")
            
            if progress_callback:
                progress_callback("Concatenating video clips...", 0.7)
            
            # Concatenate all clips
            final_video = concatenate_videoclips(clips, method="compose")
            
            if progress_callback:
                progress_callback("Writing output video file...", 0.8)
            
            # Write the final video with detailed progress tracking
            self._write_video_with_progress(
                final_video,
                output_path,
                progress_callback
            )
            
            if progress_callback:
                progress_callback("Cleaning up...", 0.95)
            
            # Clean up
            for clip in clips:
                clip.close()
            final_video.close()
            video.close()
            
            if progress_callback:
                progress_callback("Video trimming complete!", 1.0)
            
            return output_path
            
        except Exception as e:
            raise RuntimeError(f"Failed to trim video: {e}")
    
    def create_segments_preview(self, 
                              video_path: str, 
                              transcript_data: TranscriptData,
                              progress_callback: Optional[Callable[[str, float], None]] = None) -> List[Tuple[float, float, str, bool]]:
        """Create a preview of segments showing what will be kept/removed.
        
        Args:
            video_path: Path to the video file
            transcript_data: TranscriptData containing segments
            progress_callback: Optional progress callback
        
        Returns:
            List of tuples: (start_time, end_time, text, is_active)
        """
        if progress_callback:
            progress_callback("Analyzing transcript segments...", 0.0)
        
        preview_segments = []
        total_segments = len(transcript_data.segments)
        
        for i, segment in enumerate(transcript_data.segments):
            is_active = not (segment.is_filler or segment.text.strip() == "")
            
            preview_segments.append((
                segment.start_time,
                segment.end_time,
                segment.text,
                is_active
            ))
            
            if progress_callback:
                progress = (i + 1) / total_segments
                progress_callback(f"Processing segment {i + 1}/{total_segments}...", progress)
        
        return preview_segments
    
    def get_video_info(self, video_path: str) -> dict:
        """Get basic information about a video file.
        
        Args:
            video_path: Path to the video file
        
        Returns:
            Dictionary containing video information
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        try:
            with VideoFileClip(video_path) as video:
                info = {
                    'duration': video.duration,
                    'fps': video.fps,
                    'size': video.size,
                    'has_audio': video.audio is not None,
                    'file_size': os.path.getsize(video_path)
                }
                return info
        except Exception as e:
            raise RuntimeError(f"Failed to get video info: {e}")
    
    def estimate_output_duration(self, transcript_data: TranscriptData) -> float:
        """Estimate the duration of the output video after trimming.
        
        Args:
            transcript_data: TranscriptData containing segments
        
        Returns:
            Estimated duration in seconds
        """
        active_segments = transcript_data.get_active_segments()
        total_duration = sum(segment.duration() for segment in active_segments)
        return total_duration
    
    def calculate_compression_ratio(self, transcript_data: TranscriptData) -> float:
        """Calculate how much the video will be compressed (0.0 to 1.0).
        
        Args:
            transcript_data: TranscriptData containing segments
        
        Returns:
            Compression ratio (0.0 = no compression, 1.0 = maximum compression)
        """
        if transcript_data.duration <= 0:
            return 0.0
        
        output_duration = self.estimate_output_duration(transcript_data)
        compression_ratio = 1.0 - (output_duration / transcript_data.duration)
        return max(0.0, min(1.0, compression_ratio))
    
    def validate_output_path(self, output_path: str) -> None:
        """Validate that the output path is writable and has correct extension.
        
        Args:
            output_path: Path for the output file
        
        Raises:
            ValueError: If the output path is invalid
        """
        # Check if directory exists and is writable
        output_dir = os.path.dirname(output_path)
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
            except OSError as e:
                raise ValueError(f"Cannot create output directory: {e}")
        
        if not os.access(output_dir, os.W_OK):
            raise ValueError(f"Output directory is not writable: {output_dir}")
        
        # Check file extension
        _, ext = os.path.splitext(output_path.lower())
        if ext not in self.config.supported_formats:
            supported = ', '.join(self.config.supported_formats)
            raise ValueError(f"Unsupported output format '{ext}'. Supported formats: {supported}")
    
    def create_backup_segments(self, transcript_data: TranscriptData) -> TranscriptData:
        """Create a backup copy of transcript data before modifications.
        
        Args:
            transcript_data: Original transcript data
        
        Returns:
            Deep copy of the transcript data
        """
        # Create new segments list with copies
        backup_segments = []
        for segment in transcript_data.segments:
            backup_segment = TranscriptSegment(
                id=segment.id,
                start_time=segment.start_time,
                end_time=segment.end_time,
                text=segment.text,
                confidence=segment.confidence,
                is_filler=segment.is_filler
            )
            backup_segments.append(backup_segment)
        
        # Create backup transcript data
        backup_data = TranscriptData(
            segments=backup_segments,
            duration=transcript_data.duration,
            file_path=transcript_data.file_path
        )
        
        return backup_data
    
    def _write_video_with_progress(self, video_clip, output_path: str, progress_callback: Optional[Callable[[str, float], None]] = None) -> None:
        """Write video file with detailed progress tracking.
        
        Args:
            video_clip: MoviePy video clip to write
            output_path: Path for the output file
            progress_callback: Optional progress callback
        """
        import threading
        import time
        import os
        
        if not progress_callback:
            # Fallback to basic write if no progress callback
            video_clip.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                verbose=False,
                logger=None
            )
            return
        
        # Estimate output file size based on video duration and bitrate
        video_duration = video_clip.duration
        estimated_bitrate = 2000  # kbps (reasonable estimate for H.264)
        estimated_size_mb = (video_duration * estimated_bitrate) / (8 * 1024)  # Convert to MB
        
        # Progress tracking variables
        start_time = time.time()
        progress_active = threading.Event()
        progress_active.set()
        
        def progress_monitor():
            """Monitor file writing progress."""
            while progress_active.is_set():
                try:
                    if os.path.exists(output_path):
                        current_size_bytes = os.path.getsize(output_path)
                        current_size_mb = current_size_bytes / (1024 * 1024)
                        
                        # Calculate progress based on file size
                        if estimated_size_mb > 0:
                            file_progress = min(current_size_mb / estimated_size_mb, 1.0)
                        else:
                            file_progress = 0.0
                        
                        # Calculate encoding speed
                        elapsed_time = time.time() - start_time
                        if elapsed_time > 0:
                            encoding_speed = (current_size_mb / elapsed_time) if current_size_mb > 0 else 0
                            
                            # Estimate remaining time
                            if encoding_speed > 0 and file_progress < 1.0:
                                remaining_mb = estimated_size_mb - current_size_mb
                                eta_seconds = remaining_mb / encoding_speed
                                eta_text = f"ETA: {eta_seconds:.0f}s"
                            else:
                                eta_text = "ETA: calculating..."
                        else:
                            encoding_speed = 0
                            eta_text = "ETA: calculating..."
                        
                        # Update progress
                        overall_progress = 0.8 + (file_progress * 0.15)  # Map to 0.8-0.95 range
                        detail = f"Encoding: {current_size_mb:.1f}MB/{estimated_size_mb:.1f}MB ({file_progress*100:.1f}%) | Speed: {encoding_speed:.1f}MB/s | {eta_text}"
                        
                        progress_callback("Writing output video file...", overall_progress, detail)
                    else:
                        # File doesn't exist yet
                        progress_callback("Writing output video file...", 0.8, "Initializing video encoder...")
                    
                    time.sleep(0.5)  # Update every 0.5 seconds
                    
                except Exception:
                    # Ignore errors in progress monitoring
                    time.sleep(0.5)
        
        # Start progress monitoring thread
        progress_thread = threading.Thread(target=progress_monitor, daemon=True)
        progress_thread.start()
        
        try:
            # Write the video file
            video_clip.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                verbose=False,
                logger=None
            )
            
            # Final progress update
            if os.path.exists(output_path):
                final_size_mb = os.path.getsize(output_path) / (1024 * 1024)
                total_time = time.time() - start_time
                avg_speed = final_size_mb / total_time if total_time > 0 else 0
                
                detail = f"Encoding complete: {final_size_mb:.1f}MB written in {total_time:.1f}s (avg: {avg_speed:.1f}MB/s)"
                progress_callback("Video file written successfully", 0.95, detail)
            
        finally:
            # Stop progress monitoring
            progress_active.clear()
            if progress_thread.is_alive():
                progress_thread.join(timeout=2.0)
    
    def generate_output_filename(self, input_path: str, suffix: str = "_trimmed") -> str:
        """Generate an output filename based on the input filename.
        
        Args:
            input_path: Path to the input file
            suffix: Suffix to add to the filename
        
        Returns:
            Generated output filename
        """
        directory = os.path.dirname(input_path)
        filename = os.path.basename(input_path)
        name, ext = os.path.splitext(filename)
        
        output_filename = f"{name}{suffix}{ext}"
        return os.path.join(directory, output_filename)