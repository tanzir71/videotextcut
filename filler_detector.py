"""Advanced filler word detection and removal functionality."""

import re
from typing import List, Set, Dict, Tuple
from dataclasses import dataclass
from models import TranscriptSegment, TranscriptData


@dataclass
class FillerPattern:
    """Represents a filler word pattern with detection rules."""
    pattern: str
    confidence_threshold: float = 0.8
    context_sensitive: bool = False
    description: str = ""


class FillerWordDetector:
    """Advanced filler word detection with pattern matching and context analysis."""
    
    def __init__(self):
        self.filler_patterns = self._initialize_filler_patterns()
        self.silence_threshold = 0.5  # seconds of silence to consider as empty spot
        self.min_segment_duration = 0.3  # minimum duration for a valid segment
    
    def _initialize_filler_patterns(self) -> List[FillerPattern]:
        """Initialize comprehensive filler word patterns."""
        patterns = [
            # Basic filler words
            FillerPattern(r'\buh+\b', 0.9, False, "Basic 'uh' filler"),
            FillerPattern(r'\bum+\b', 0.9, False, "Basic 'um' filler"),
            FillerPattern(r'\buhmm?\b', 0.9, False, "'Uhm' variations"),
            FillerPattern(r'\buhh+\b', 0.9, False, "Extended 'uh' sounds"),
            
            # Extended filler sounds
            FillerPattern(r'\bah+\b', 0.8, True, "'Ah' hesitation sounds"),
            FillerPattern(r'\boh+\b', 0.7, True, "'Oh' hesitation sounds"),
            FillerPattern(r'\beh+\b', 0.8, False, "'Eh' filler sounds"),
            FillerPattern(r'\bmm+\b', 0.8, False, "'Mm' thinking sounds"),
            FillerPattern(r'\bhmm+\b', 0.8, False, "'Hmm' thinking sounds"),
            
            # Repetitive words and phrases
            FillerPattern(r'\b(like)\s+\1\b', 0.8, True, "Repeated 'like'"),
            FillerPattern(r'\b(you know)\s+\1\b', 0.8, True, "Repeated 'you know'"),
            FillerPattern(r'\b(I mean)\s+\1\b', 0.8, True, "Repeated 'I mean'"),
            
            # Common filler phrases
            FillerPattern(r'\byou know\b', 0.7, True, "'You know' filler phrase"),
            FillerPattern(r'\bi mean\b', 0.7, True, "'I mean' filler phrase"),
            FillerPattern(r'\blike\b(?!\s+(this|that|it|he|she|they|we|I))', 0.6, True, "Standalone 'like'"),
            FillerPattern(r'\bso\b(?=\s+(uh|um|like|you know))', 0.7, True, "'So' before fillers"),
            FillerPattern(r'\bwell\b(?=\s*(uh|um|like))', 0.7, True, "'Well' before fillers"),
            
            # Stuttering patterns
            FillerPattern(r'\b(\w)\1{2,}\b', 0.8, False, "Stuttering (repeated letters)"),
            FillerPattern(r'\b(\w+)\s+\1\b', 0.8, True, "Word repetition"),
            
            # False starts and corrections
            FillerPattern(r'\bI\s+I\b', 0.8, False, "Repeated 'I'"),
            FillerPattern(r'\bthe\s+the\b', 0.8, False, "Repeated 'the'"),
            FillerPattern(r'\band\s+and\b', 0.8, False, "Repeated 'and'"),
            
            # Breathing and mouth sounds
            FillerPattern(r'\b\*[^\*]*\*\b', 0.9, False, "Marked non-speech sounds"),
            FillerPattern(r'\[.*?\]', 0.9, False, "Bracketed non-speech sounds"),
        ]
        
        return patterns
    
    def detect_filler_words(self, transcript_data: TranscriptData, 
                          custom_filler_words: List[str] = None) -> None:
        """Detect and mark filler words in transcript segments.
        
        Args:
            transcript_data: TranscriptData object to process
            custom_filler_words: Additional custom filler words to detect
        """
        if custom_filler_words:
            self._add_custom_patterns(custom_filler_words)
        
        for segment in transcript_data.segments:
            if self._is_filler_segment(segment):
                segment.is_filler = True
    
    def _add_custom_patterns(self, custom_words: List[str]) -> None:
        """Add custom filler word patterns.
        
        Args:
            custom_words: List of custom filler words to add
        """
        for word in custom_words:
            # Escape special regex characters and create pattern
            escaped_word = re.escape(word.lower())
            pattern = f'\\b{escaped_word}\\b'
            
            custom_pattern = FillerPattern(
                pattern=pattern,
                confidence_threshold=0.8,
                context_sensitive=False,
                description=f"Custom filler word: '{word}'"
            )
            
            self.filler_patterns.append(custom_pattern)
    
    def _is_filler_segment(self, segment: TranscriptSegment) -> bool:
        """Determine if a segment contains filler words.
        
        Args:
            segment: TranscriptSegment to analyze
        
        Returns:
            True if segment is considered filler
        """
        # Check for empty or very short segments
        if not segment.text.strip() or segment.duration() < self.min_segment_duration:
            return True
        
        # Check for low confidence segments
        if segment.confidence < 0.3:
            return True
        
        # Normalize text for pattern matching
        normalized_text = self._normalize_text(segment.text)
        
        # Check against filler patterns
        for pattern in self.filler_patterns:
            if self._matches_pattern(normalized_text, pattern, segment):
                return True
        
        # Check for segments that are mostly non-alphabetic
        if self._is_mostly_non_speech(normalized_text):
            return True
        
        return False
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for pattern matching.
        
        Args:
            text: Raw text to normalize
        
        Returns:
            Normalized text
        """
        # Convert to lowercase
        normalized = text.lower()
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        # Remove punctuation at word boundaries for better matching
        normalized = re.sub(r'\b[^\w\s]+\b', ' ', normalized)
        
        return normalized
    
    def _matches_pattern(self, text: str, pattern: FillerPattern, 
                        segment: TranscriptSegment) -> bool:
        """Check if text matches a filler pattern.
        
        Args:
            text: Normalized text to check
            pattern: FillerPattern to match against
            segment: Original segment for context
        
        Returns:
            True if pattern matches
        """
        # Check confidence threshold
        if segment.confidence < pattern.confidence_threshold:
            return False
        
        # Check pattern match
        match = re.search(pattern.pattern, text, re.IGNORECASE)
        if not match:
            return False
        
        # For context-sensitive patterns, do additional checks
        if pattern.context_sensitive:
            return self._validate_context(text, match, pattern)
        
        return True
    
    def _validate_context(self, text: str, match: re.Match, 
                         pattern: FillerPattern) -> bool:
        """Validate context for context-sensitive patterns.
        
        Args:
            text: Full text being analyzed
            match: Regex match object
            pattern: FillerPattern being validated
        
        Returns:
            True if context validates the filler detection
        """
        matched_text = match.group(0)
        
        # Special handling for "like"
        if "like" in pattern.pattern:
            return self._validate_like_context(text, match)
        
        # Special handling for "you know"
        if "you know" in pattern.pattern:
            return self._validate_you_know_context(text, match)
        
        # Special handling for "ah" and "oh"
        if pattern.pattern in [r'\bah+\b', r'\boh+\b']:
            return self._validate_exclamation_context(text, match)
        
        # Default: if it's a short segment with mostly the filler, it's likely filler
        return len(text.split()) <= 3
    
    def _validate_like_context(self, text: str, match: re.Match) -> bool:
        """Validate 'like' usage context.
        
        Args:
            text: Full text
            match: Match object for 'like'
        
        Returns:
            True if 'like' is used as filler
        """
        # Get surrounding context
        start, end = match.span()
        before = text[:start].strip().split()[-2:] if start > 0 else []
        after = text[end:].strip().split()[:2] if end < len(text) else []
        
        # "Like" is likely filler if:
        # 1. It's at the beginning of a sentence
        # 2. It's followed by another filler word
        # 3. It's in a very short segment
        # 4. It's repeated
        
        if not before:  # Beginning of segment
            return True
        
        if after and after[0] in ['uh', 'um', 'you', 'i']:
            return True
        
        if len(text.split()) <= 2:
            return True
        
        return False
    
    def _validate_you_know_context(self, text: str, match: re.Match) -> bool:
        """Validate 'you know' usage context.
        
        Args:
            text: Full text
            match: Match object for 'you know'
        
        Returns:
            True if 'you know' is used as filler
        """
        # "You know" is often filler when:
        # 1. It's at the end of a segment
        # 2. It's in a short segment
        # 3. It's not followed by substantive content
        
        start, end = match.span()
        after = text[end:].strip()
        
        # If nothing meaningful follows, it's likely filler
        if not after or len(after.split()) <= 1:
            return True
        
        # If the segment is very short, it's likely filler
        if len(text.split()) <= 4:
            return True
        
        return False
    
    def _validate_exclamation_context(self, text: str, match: re.Match) -> bool:
        """Validate 'ah'/'oh' exclamation context.
        
        Args:
            text: Full text
            match: Match object
        
        Returns:
            True if it's a filler rather than meaningful exclamation
        """
        # Short segments with just "ah" or "oh" are likely filler
        return len(text.split()) <= 2
    
    def _is_mostly_non_speech(self, text: str) -> bool:
        """Check if text is mostly non-speech sounds.
        
        Args:
            text: Text to analyze
        
        Returns:
            True if text is mostly non-speech
        """
        # Count alphabetic characters vs total characters
        alpha_chars = sum(1 for c in text if c.isalpha())
        total_chars = len(text.replace(' ', ''))
        
        if total_chars == 0:
            return True
        
        alpha_ratio = alpha_chars / total_chars
        return alpha_ratio < 0.5
    
    def detect_empty_spots(self, transcript_data: TranscriptData, 
                          silence_threshold: float = None) -> List[Tuple[float, float]]:
        """Detect empty spots (gaps) in the transcript.
        
        Args:
            transcript_data: TranscriptData to analyze
            silence_threshold: Minimum gap duration to consider as empty spot
        
        Returns:
            List of (start_time, end_time) tuples for empty spots
        """
        if silence_threshold is None:
            silence_threshold = self.silence_threshold
        
        empty_spots = []
        
        # Sort segments by start time
        sorted_segments = sorted(transcript_data.segments, key=lambda s: s.start_time)
        
        for i in range(len(sorted_segments) - 1):
            current_end = sorted_segments[i].end_time
            next_start = sorted_segments[i + 1].start_time
            
            gap_duration = next_start - current_end
            
            if gap_duration >= silence_threshold:
                empty_spots.append((current_end, next_start))
        
        return empty_spots
    
    def get_filler_statistics(self, transcript_data: TranscriptData) -> Dict[str, any]:
        """Get statistics about filler words in the transcript.
        
        Args:
            transcript_data: TranscriptData to analyze
        
        Returns:
            Dictionary containing filler statistics
        """
        total_segments = len(transcript_data.segments)
        filler_segments = sum(1 for s in transcript_data.segments if s.is_filler)
        
        total_duration = transcript_data.duration
        filler_duration = sum(s.duration() for s in transcript_data.segments if s.is_filler)
        
        # Analyze filler types
        filler_types = {}
        for segment in transcript_data.segments:
            if segment.is_filler:
                normalized_text = self._normalize_text(segment.text)
                for pattern in self.filler_patterns:
                    if re.search(pattern.pattern, normalized_text, re.IGNORECASE):
                        filler_types[pattern.description] = filler_types.get(pattern.description, 0) + 1
                        break
        
        return {
            'total_segments': total_segments,
            'filler_segments': filler_segments,
            'filler_percentage': (filler_segments / total_segments * 100) if total_segments > 0 else 0,
            'total_duration': total_duration,
            'filler_duration': filler_duration,
            'filler_time_percentage': (filler_duration / total_duration * 100) if total_duration > 0 else 0,
            'filler_types': filler_types,
            'empty_spots': self.detect_empty_spots(transcript_data)
        }
    
    def suggest_improvements(self, transcript_data: TranscriptData) -> List[str]:
        """Suggest improvements based on filler analysis.
        
        Args:
            transcript_data: TranscriptData to analyze
        
        Returns:
            List of improvement suggestions
        """
        stats = self.get_filler_statistics(transcript_data)
        suggestions = []
        
        if stats['filler_percentage'] > 30:
            suggestions.append("High filler word usage detected. Consider practicing speech without fillers.")
        
        if stats['filler_time_percentage'] > 20:
            suggestions.append("Filler words take up significant time. Removing them will greatly shorten the video.")
        
        if len(stats['empty_spots']) > 5:
            suggestions.append("Multiple silent gaps detected. Consider removing long pauses.")
        
        # Analyze most common filler types
        if stats['filler_types']:
            most_common = max(stats['filler_types'].items(), key=lambda x: x[1])
            suggestions.append(f"Most common filler type: {most_common[0]} ({most_common[1]} occurrences)")
        
        return suggestions