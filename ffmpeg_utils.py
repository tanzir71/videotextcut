"""FFmpeg utility functions for video processing."""

import os
import sys
import subprocess
import platform
from typing import Optional, Tuple
import logging


class FFmpegError(Exception):
    """Custom exception for FFmpeg-related errors."""
    pass


class FFmpegUtils:
    """Utility class for FFmpeg detection and management."""
    
    @staticmethod
    def is_ffmpeg_available() -> bool:
        """Check if FFmpeg is available in the system PATH.
        
        Returns:
            True if FFmpeg is available, False otherwise
        """
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    @staticmethod
    def get_ffmpeg_version() -> Optional[str]:
        """Get FFmpeg version if available.
        
        Returns:
            FFmpeg version string or None if not available
        """
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                # Extract version from first line
                first_line = result.stdout.split('\n')[0]
                if 'ffmpeg version' in first_line:
                    return first_line.split('ffmpeg version ')[1].split(' ')[0]
            return None
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            return None
    
    @staticmethod
    def get_installation_instructions() -> str:
        """Get platform-specific FFmpeg installation instructions.
        
        Returns:
            Formatted installation instructions
        """
        system = platform.system().lower()
        
        if system == 'windows':
            return (
                "FFmpeg Installation Instructions for Windows:\n\n"
                "Option 1 - Using Chocolatey (Recommended):\n"
                "1. Install Chocolatey from https://chocolatey.org/install\n"
                "2. Open PowerShell as Administrator\n"
                "3. Run: choco install ffmpeg\n\n"
                "Option 2 - Manual Installation:\n"
                "1. Download FFmpeg from https://ffmpeg.org/download.html\n"
                "2. Extract the files to C:\\ffmpeg\n"
                "3. Add C:\\ffmpeg\\bin to your system PATH\n"
                "4. Restart your command prompt/application\n\n"
                "Option 3 - Using Scoop:\n"
                "1. Install Scoop from https://scoop.sh/\n"
                "2. Run: scoop install ffmpeg\n\n"
                "After installation, restart this application."
            )
        elif system == 'darwin':  # macOS
            return (
                "FFmpeg Installation Instructions for macOS:\n\n"
                "Option 1 - Using Homebrew (Recommended):\n"
                "1. Install Homebrew from https://brew.sh/\n"
                "2. Run: brew install ffmpeg\n\n"
                "Option 2 - Using MacPorts:\n"
                "1. Install MacPorts from https://www.macports.org/\n"
                "2. Run: sudo port install ffmpeg\n\n"
                "After installation, restart this application."
            )
        else:  # Linux and others
            return (
                "FFmpeg Installation Instructions for Linux:\n\n"
                "Ubuntu/Debian:\n"
                "sudo apt update && sudo apt install ffmpeg\n\n"
                "CentOS/RHEL/Fedora:\n"
                "sudo dnf install ffmpeg  # or sudo yum install ffmpeg\n\n"
                "Arch Linux:\n"
                "sudo pacman -S ffmpeg\n\n"
                "After installation, restart this application."
            )
    
    @staticmethod
    def check_ffmpeg_and_raise() -> None:
        """Check if FFmpeg is available and raise detailed error if not.
        
        Raises:
            FFmpegError: If FFmpeg is not available with installation instructions
        """
        if not FFmpegUtils.is_ffmpeg_available():
            instructions = FFmpegUtils.get_installation_instructions()
            error_msg = (
                "FFmpeg is required but not found on your system.\n\n"
                "FFmpeg is needed for video processing operations including:\n"
                "• Audio extraction from video files\n"
                "• Video format conversion\n"
                "• Video trimming and editing\n\n"
                f"{instructions}"
            )
            raise FFmpegError(error_msg)
    
    @staticmethod
    def get_ffmpeg_info() -> Tuple[bool, Optional[str], str]:
        """Get comprehensive FFmpeg information.
        
        Returns:
            Tuple of (is_available, version, installation_instructions)
        """
        is_available = FFmpegUtils.is_ffmpeg_available()
        version = FFmpegUtils.get_ffmpeg_version() if is_available else None
        instructions = FFmpegUtils.get_installation_instructions()
        
        return is_available, version, instructions
    
    @staticmethod
    def log_ffmpeg_status() -> None:
        """Log current FFmpeg status for debugging."""
        logger = logging.getLogger(__name__)
        
        is_available, version, _ = FFmpegUtils.get_ffmpeg_info()
        
        if is_available:
            logger.info(f"FFmpeg is available - Version: {version}")
        else:
            logger.warning("FFmpeg is not available on this system")
            logger.info("Video processing features will not work without FFmpeg")