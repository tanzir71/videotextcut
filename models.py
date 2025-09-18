"""Data models for the VideoTextCut application."""

from dataclasses import dataclass, field
from typing import List, Optional
import re


@dataclass
class WordTiming:
    """Represents timing information for a single word."""
    word: str
    start_time: float
    end_time: float
    confidence: float = 0.0


@dataclass
class TranscriptSegment:
    """Represents a single segment of transcript with timing information."""
    id: int
    start_time: float  # seconds
    end_time: float    # seconds
    text: str
    is_filler: bool = False
    is_deleted: bool = False
    confidence: float = 0.0
    word_timings: List['WordTiming'] = field(default_factory=list)

    def duration(self) -> float:
        """Get the duration of this segment in seconds."""
        return self.end_time - self.start_time
    
    def get_active_word_ranges(self, edited_text: str) -> List[tuple]:
        """Get time ranges for words that remain in the edited text."""
        if not self.word_timings:
            # Fallback: if no word timings, return full segment if text matches
            if edited_text.strip().lower() in self.text.lower():
                return [(self.start_time, self.end_time)]
            return []
        
        active_ranges = []
        edited_words = edited_text.lower().split()
        original_words = [wt.word.lower() for wt in self.word_timings]
        
        # Find continuous ranges of matching words
        i = 0
        while i < len(edited_words):
            # Find where this edited word appears in original
            word = edited_words[i]
            try:
                start_idx = original_words.index(word, i if i < len(original_words) else 0)
                
                # Find continuous sequence
                end_idx = start_idx
                j = i + 1
                while (j < len(edited_words) and 
                       end_idx + 1 < len(original_words) and 
                       edited_words[j].lower() == original_words[end_idx + 1].lower()):
                    end_idx += 1
                    j += 1
                
                # Add time range for this sequence
                if start_idx < len(self.word_timings) and end_idx < len(self.word_timings):
                    range_start = self.word_timings[start_idx].start_time
                    range_end = self.word_timings[end_idx].end_time
                    active_ranges.append((range_start, range_end))
                
                i = j
            except ValueError:
                # Word not found, skip it
                i += 1
        
        return active_ranges




@dataclass
class TranscriptData:
    """Container for all transcript segments and metadata."""
    segments: List[TranscriptSegment]
    duration: float
    file_path: str
    
    def get_active_segments(self) -> List[TranscriptSegment]:
        """Get segments that are not deleted."""
        return [segment for segment in self.segments if not getattr(segment, 'is_deleted', False)]
    

    
    def get_total_active_duration(self) -> float:
        """Get total duration of active (non-deleted) segments."""
        return sum(seg.duration() for seg in self.get_active_segments())
    
    def remove_filler_segments(self) -> None:
        """Mark all filler segments as deleted."""
        for segment in self.segments:
            if segment.is_filler:
                segment.is_deleted = True
    
    def get_text_content(self, include_timestamps: bool = False) -> str:
        """Get the full text content of active segments."""
        active_segments = self.get_active_segments()
        if include_timestamps:
            lines = []
            for seg in active_segments:
                timestamp = f"[{seg.start_time:.2f}s - {seg.end_time:.2f}s]"
                lines.append(f"{timestamp} {seg.text}")
            return "\n".join(lines)
        else:
            return " ".join(seg.text for seg in active_segments)
    
    def update_from_text(self, edited_text: str) -> None:
        """Update segments based on edited text content with word-level precision."""
        lines = [line.strip() for line in edited_text.split('\n') if line.strip()]
        
        # Reset all segments to not deleted
        for seg in self.segments:
            seg.is_deleted = False
        
        # Parse each line and update corresponding segments
        current_segment = None
        segment_text_parts = []
        
        for line in lines:
            # Check if line is a timestamp
            if line.startswith('[') and line.endswith(']') and 's -' in line:
                # Process previous segment if exists
                if current_segment and segment_text_parts:
                    edited_segment_text = ' '.join(segment_text_parts).strip()
                    if not edited_segment_text:
                        # If segment text is empty, mark as deleted
                        current_segment.is_deleted = True
                    else:
                        # Update segment text and calculate active ranges
                        current_segment.text = edited_segment_text
                
                # Find the segment with matching timestamp
                try:
                    timestamp_part = line[1:-1]  # Remove brackets
                    start_time_str = timestamp_part.split('s -')[0]
                    start_time = float(start_time_str)
                    
                    # Find matching segment
                    current_segment = None
                    for segment in self.segments:
                        if abs(segment.start_time - start_time) < 0.1:  # Allow small tolerance
                            current_segment = segment
                            segment_text_parts = []
                            break
                except (ValueError, IndexError):
                    current_segment = None
                    segment_text_parts = []
            else:
                # Add to current segment text
                if current_segment is not None:
                    segment_text_parts.append(line)
        
        # Process last segment
        if current_segment and segment_text_parts:
            edited_segment_text = ' '.join(segment_text_parts).strip()
            if not edited_segment_text:
                current_segment.is_deleted = True
            else:
                current_segment.text = edited_segment_text
    
    def get_active_time_ranges(self) -> List[tuple]:
        """Get all active time ranges for video trimming."""
        active_ranges = []
        
        for segment in self.segments:
            if not segment.is_deleted:
                # For segments with word timings, get precise ranges
                if segment.word_timings:
                    word_ranges = segment.get_active_word_ranges(segment.text)
                    active_ranges.extend(word_ranges)
                else:
                    # Fallback to full segment
                    active_ranges.append((segment.start_time, segment.end_time))
        
        # Merge overlapping ranges
        if not active_ranges:
            return []
        
        active_ranges.sort()
        merged_ranges = [active_ranges[0]]
        
        for start, end in active_ranges[1:]:
            last_start, last_end = merged_ranges[-1]
            if start <= last_end + 0.1:  # Small gap tolerance
                merged_ranges[-1] = (last_start, max(last_end, end))
            else:
                merged_ranges.append((start, end))
        
        return merged_ranges


@dataclass
class AppConfig:
    """Application configuration settings."""
    supported_formats: List[str] = field(default_factory=lambda: ['.mp4', '.avi', '.mov', '.mkv', '.m4v', '.webm'])
    whisper_model: str = 'base'  # tiny, base, small, medium, large
    output_format: str = 'mp4'
    silence_threshold: float = 0.01  # for detecting silent segments
    min_segment_duration: float = 0.5  # minimum segment length in seconds
    filler_words: List[str] = field(default_factory=lambda: [
        'uh', 'um', 'uhm', 'er', 'ah', 'like', 'you know', 'so', 'well', 'actually'
    ])
    output_directory: str = 'output'
    temp_directory: str = 'temp'
    
    # Video processing settings
    DEFAULT_OUTPUT_FORMAT = 'mp4'
    DEFAULT_AUDIO_CODEC = 'aac'
    DEFAULT_VIDEO_CODEC = 'libx264'
    
    # GUI settings
    window_width: int = 1200
    window_height: int = 800
    min_window_width: int = 800
    min_window_height: int = 600
    
    # Colors (from requirements)
    primary_color: str = '#2196F3'
    text_color: str = '#333333'
    background_color: str = '#F5F5F5'
    error_color: str = '#F44336'
    success_color: str = '#4CAF50'
    
    @property
    def gui_colors(self) -> dict:
        """Get GUI color scheme as dictionary."""
        return {
            'primary': self.primary_color,
            'text': self.text_color,
            'background': self.background_color,
            'error': self.error_color,
            'success': self.success_color
        }
    
    def get_supported_file_filter(self) -> str:
        """Get file filter string for file dialogs."""
        extensions = ';'.join(f'*{ext}' for ext in self.supported_formats)
        return f"Video files ({extensions})"