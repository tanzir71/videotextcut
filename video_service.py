"""Video processing service using MoviePy for trimming and editing."""

import os
import tempfile
import subprocess
import shutil
from typing import List, Tuple, Optional, Callable
from moviepy.editor import VideoFileClip, concatenate_videoclips
from models import TranscriptData, TranscriptSegment, AppConfig
from ffmpeg_utils import FFmpegUtils, FFmpegError


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
            
            # Debug logging to help diagnose repetition issues
            print(f"DEBUG: Found {len(active_ranges)} active ranges:")
            for i, (start, end) in enumerate(active_ranges):
                print(f"  Range {i+1}: {start:.3f}s - {end:.3f}s (duration: {end-start:.3f}s)")
            
            # Attempt fast trim (no re-encode) if enabled
            if getattr(self.config, 'prefer_fast_trim', False):
                try:
                    if progress_callback:
                        progress_callback("Attempting fast trim (no re-encode)...", 0.25, "Using FFmpeg stream copy for keyframe-aligned cuts")
                    print("DEBUG: Using fast trim (stream copy) pipeline")
                    self._fast_trim_stream_copy(video_path, active_ranges, output_path, progress_callback)
                    # Cleanup video object since we won't use MoviePy path
                    video.close()
                    if progress_callback:
                        progress_callback("Fast trim complete!", 1.0, None)
                    return output_path
                except Exception as fe:
                    # Fall back to re-encode path
                    print(f"DEBUG: Fast trim failed, falling back to re-encode: {fe}")
                    if progress_callback:
                        progress_callback("Fast trim unavailable, falling back to standard encoding...", 0.28, str(fe))
                    # Ensure video object is still valid for fallback
                    if video.reader is None or video.reader.closed:
                        print("DEBUG: Reloading video for fallback")
                        video.close()
                        video = VideoFileClip(video_path)
            else:
                print("DEBUG: Using standard re-encode pipeline")
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
            
            # Choose faster concat method when possible
            concat_method = "compose"
            try:
                base_size = clips[0].size if hasattr(clips[0], 'size') else None
                base_fps = getattr(clips[0], 'fps', None)
                same_size = all((getattr(c, 'size', None) == base_size) for c in clips)
                same_fps = all((getattr(c, 'fps', None) == base_fps) for c in clips)
                if same_size and same_fps and base_size is not None and base_fps is not None:
                    concat_method = "chain"  # much faster, avoids compositing
            except Exception:
                concat_method = "compose"
            
            # Concatenate all clips
            final_video = concatenate_videoclips(clips, method=concat_method)
            
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

    def _parse_bitrate_kbps(self, bitrate_str: Optional[str]) -> Optional[float]:
        """Parse bitrate like '3000k' to kbps float."""
        if not bitrate_str:
            return None
        try:
            s = bitrate_str.strip().lower()
            if s.endswith('k'):
                return float(s[:-1])
            if s.endswith('m'):
                return float(s[:-1]) * 1024.0
            return float(s) / 1000.0
        except Exception:
            return None

    def _build_encoding_params(self, codec: str):
        """Build MoviePy/ffmpeg encoding parameters based on AppConfig and codec."""
        preset = self.config.ffmpeg_preset
        threads = self.config.threads
        audio_bitrate = self.config.audio_bitrate
        bitrate = self.config.target_bitrate
        ffmpeg_params: List[str] = ['-movflags', '+faststart']  # better playback start
        
        # CRF if no explicit target bitrate and CPU codec
        if codec in ('libx264', 'libx265'):
            if not bitrate:
                ffmpeg_params += ['-crf', f'{self.config.crf}']
            # Ensure compatibility pixel format
            ffmpeg_params += ['-pix_fmt', 'yuv420p']
        
        # NVENC specific tweaks can be added here if needed
        return {
            'codec': codec,
            'audio_codec': 'aac',
            'preset': preset,
            'threads': threads,
            'bitrate': bitrate,
            'audio_bitrate': audio_bitrate,
            'ffmpeg_params': ffmpeg_params,
        }

    def _candidate_codecs(self) -> List[str]:
        """Return a prioritized list of codecs to try for faster encoding."""
        candidates: List[str] = []
        if getattr(self.config, 'prefer_gpu_encoding', False):
            candidates.extend(self.config.gpu_codecs)
        # Always fall back to CPU x264, which is widely available
        candidates.append('libx264')
        return candidates
    
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
        
        # Helper to attempt write with a specific codec
        def attempt_write(codec: str) -> None:
            params = self._build_encoding_params(codec)
            # Call MoviePy with our tuned parameters
            video_clip.write_videofile(
                output_path,
                codec=params['codec'],
                audio_codec=params['audio_codec'],
                preset=params['preset'],
                threads=params['threads'],
                bitrate=params['bitrate'],
                audio_bitrate=params['audio_bitrate'],
                ffmpeg_params=params['ffmpeg_params'],
                verbose=False,
                logger=None
            )
        
        if not progress_callback:
            # Fallback to basic write with fast params if no progress callback
            last_error: Optional[Exception] = None
            for codec in self._candidate_codecs():
                try:
                    attempt_write(codec)
                    return
                except Exception as e:
                    last_error = e
                    # Clean up partial file before next attempt
                    try:
                        if os.path.exists(output_path):
                            os.remove(output_path)
                    except Exception:
                        pass
            # If all attempts failed, raise last error
            raise last_error if last_error else RuntimeError('Failed to encode video')
        
        # Estimate output file size based on duration and target/estimated bitrate
        video_duration = video_clip.duration or 0
        target_kbps = self._parse_bitrate_kbps(self.config.target_bitrate) or 2000.0
        estimated_size_mb = (video_duration * target_kbps) / (8 * 1024)  # Convert to MB
        
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
        
        last_error: Optional[Exception] = None
        try:
            for idx, codec in enumerate(self._candidate_codecs()):
                try:
                    # Inform about codec choice
                    progress_callback("Writing output video file...", 0.8, f"Using codec: {codec} (attempt {idx+1})")
                    attempt_write(codec)
                    # Final progress update
                    if os.path.exists(output_path):
                        final_size_mb = os.path.getsize(output_path) / (1024 * 1024)
                        total_time = time.time() - start_time
                        avg_speed = final_size_mb / total_time if total_time > 0 else 0
                        
                        detail = f"Encoding complete: {final_size_mb:.1f}MB written in {total_time:.1f}s (avg: {avg_speed:.1f}MB/s)"
                        progress_callback("Video file written successfully", 0.95, detail)
                    return
                except Exception as e:
                    last_error = e
                    # Inform and try next codec
                    progress_callback("Writing output video file...", 0.85, f"Codec {codec} failed, trying next... ({e})")
                    # Remove partial file to avoid confusion
                    try:
                        if os.path.exists(output_path):
                            os.remove(output_path)
                    except Exception:
                        pass
            # If exhausted all codecs
            raise last_error if last_error else RuntimeError('Failed to encode video')
        finally:
            # Stop progress monitoring
            progress_active.clear()
            if progress_thread.is_alive():
                progress_thread.join(timeout=2.0)

    def _fast_trim_stream_copy(self, video_path: str, active_ranges: List[Tuple[float, float]], output_path: str, 
                               progress_callback: Optional[Callable[[str, float, Optional[str]], None]] = None) -> None:
        """Perform fast trimming using FFmpeg stream copy (no re-encode).
        
        This method cuts segments using keyframe-aligned seeking and concatenates them without re-encoding.
        It is very fast but cuts may be slightly off if start times are not near keyframes.
        """
        # Ensure output file doesn't exist to prevent append issues
        if os.path.exists(output_path):
            print(f"DEBUG: Removing existing output file: {output_path}")
            try:
                os.remove(output_path)
            except Exception as e:
                print(f"DEBUG: Could not remove existing output file: {e}")
        
        # Ensure FFmpeg is available
        try:
            FFmpegUtils.check_ffmpeg_and_raise()
        except FFmpegError as e:
            raise RuntimeError(str(e))
        
        # Debug: Print active ranges before processing
        print(f"DEBUG: Processing {len(active_ranges)} active ranges:")
        for i, (start, end) in enumerate(active_ranges):
            print(f"  Range {i+1}: {start:.3f}s - {end:.3f}s (duration: {end-start:.3f}s)")
        
        # Check for potential duplicates or overlaps
        for i in range(len(active_ranges)):
            for j in range(i+1, len(active_ranges)):
                start1, end1 = active_ranges[i]
                start2, end2 = active_ranges[j]
                if (start1 == start2 and end1 == end2):
                    print(f"DEBUG: WARNING - Duplicate ranges found: Range {i+1} and Range {j+1}")
                elif not (end1 <= start2 or end2 <= start1):  # Overlapping
                    overlap_start = max(start1, start2)
                    overlap_end = min(end1, end2)
                    print(f"DEBUG: WARNING - Overlapping ranges: Range {i+1} and Range {j+1}, overlap: {overlap_start:.3f}s - {overlap_end:.3f}s")
        
        # Prepare temporary directory for segment files
        temp_dir = tempfile.mkdtemp(prefix="fasttrim_")
        segments: List[str] = []
        list_file_path = os.path.join(temp_dir, "concat_list.txt")
        
        # Create segments
        total = len(active_ranges)
        prev_end: Optional[float] = None
        overlap_guard = 0.02  # 20 ms guard to prevent duplicated content at joins
        for idx, (start, end) in enumerate(active_ranges, start=1):
            start = max(0.0, float(start))
            end = max(start, float(end))
            # Prevent overlaps that can cause repeated content due to keyframe snapping
            if prev_end is not None and start < prev_end + overlap_guard:
                start = min(end, prev_end + overlap_guard)
            duration = max(0.0, end - start)
            if duration <= 0:
                prev_end = end
                continue
            seg_path = os.path.join(temp_dir, f"seg_{idx:04d}.ts")
            # Build ffmpeg command to copy streams into MPEG-TS
            # Use output seeking (-ss after -i) for more precise cuts at the cost of some speed
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-ss', f'{start:.3f}',  # Output seeking for precision
                '-t', f'{duration:.3f}',
                '-c', 'copy',
                '-avoid_negative_ts', 'make_zero',
                '-reset_timestamps', '1',
                '-muxdelay', '0',
                '-muxpreload', '0',
                '-f', 'mpegts',
                seg_path
            ]
            print(f"DEBUG: Cutting segment {idx}: {start:.3f}s-{end:.3f}s (duration: {duration:.3f}s)")
            print(f"DEBUG: FFmpeg command: {' '.join(cmd)}")
            if progress_callback:
                progress_callback("Cutting segments (fast mode)...", 0.25 + 0.45 * (idx-1)/max(1,total), f"Segment {idx}/{total}: {start:.2f}s → {end:.2f}s")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                # Cleanup partial segments before raising
                stderr_tail = (result.stderr or '')[-500:]
                self._cleanup_fasttrim(temp_dir)
                raise RuntimeError(f"FFmpeg failed to cut segment {idx}: {stderr_tail}")
            segments.append(seg_path)
            prev_end = end
        
        if not segments:
            self._cleanup_fasttrim(temp_dir)
            raise RuntimeError("No segments were created for fast trim")
        
        # Write concat list file
        with open(list_file_path, 'w', encoding='utf-8') as f:
            print(f"DEBUG: Writing concat list with {len(segments)} segments:")
            for i, seg in enumerate(segments):
                # ffmpeg concat demuxer expects: file 'path'
                f.write(f"file '{seg}'\n")
                print(f"  Segment {i+1}: {seg}")
        
        # Debug: Show concat list contents
        print(f"DEBUG: Concat list file contents:")
        with open(list_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            print(content)
        
        # Build concat command
        def run_concat(use_bsf: bool) -> subprocess.CompletedProcess:
            concat_cmd = [
                'ffmpeg', '-y',
                '-f', 'concat', '-safe', '0',
                '-i', list_file_path,
                '-fflags', '+genpts',
                '-c', 'copy'
            ]
            if use_bsf:
                concat_cmd += ['-bsf:a', 'aac_adtstoasc']
            concat_cmd += [output_path]
            return subprocess.run(concat_cmd, capture_output=True, text=True)
        
        if progress_callback:
            progress_callback("Concatenating segments (fast mode)...", 0.72, None)
        
        result = run_concat(use_bsf=True)
        if result.returncode != 0:
            # Try again without audio bitstream filter (for non-AAC audio)
            result2 = run_concat(use_bsf=False)
            if result2.returncode != 0:
                stderr_tail = (result2.stderr or result.stderr or '')[-800:]
                self._cleanup_fasttrim(temp_dir)
                raise RuntimeError(f"FFmpeg concat failed: {stderr_tail}")
        
        # Cleanup temporary files
        self._cleanup_fasttrim(temp_dir)
        
        if progress_callback:
            progress_callback("Fast trim output written", 0.95, None)

    def _cleanup_fasttrim(self, temp_dir: str) -> None:
        try:
            if os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
    
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