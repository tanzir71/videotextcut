#!/usr/bin/env python3
"""Main entry point for the VideoTextCut application."""

import sys
import os
import logging
import tkinter as tk
from tkinter import messagebox
import threading
from pathlib import Path

# Add current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from models import AppConfig
    from gui import VideoTranscriptApp
    from transcript_service import TranscriptService
    from video_service import VideoService
    from filler_detector import FillerWordDetector
    from progress_tracker import get_global_tracker
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Please ensure all required dependencies are installed.")
    print("Run: pip install -r requirements.txt")
    sys.exit(1)


def setup_logging(log_level: str = "INFO") -> None:
    """Setup application logging.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configure logging
    log_file = log_dir / "video_transcript_app.log"
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set specific loggers to reduce noise
    logging.getLogger('matplotlib').setLevel(logging.WARNING)
    logging.getLogger('PIL').setLevel(logging.WARNING)
    logging.getLogger('moviepy').setLevel(logging.WARNING)


def check_dependencies() -> bool:
    """Check if all required dependencies are available.
    
    Returns:
        True if all dependencies are available, False otherwise
    """
    required_modules = [
        ('whisper', 'OpenAI Whisper'),
        ('moviepy.editor', 'MoviePy'),
        ('numpy', 'NumPy'),
        ('tkinter', 'Tkinter (should be included with Python)'),
    ]
    
    # Check FFmpeg availability
    try:
        from ffmpeg_utils import FFmpegUtils
        if not FFmpegUtils.is_ffmpeg_available():
            error_msg = (
                "FFmpeg is required but not installed on your system.\n\n" +
                FFmpegUtils.get_installation_instructions() +
                "\n\nPlease install FFmpeg and restart the application."
            )
            
            # Try to show GUI error if tkinter is available
            try:
                root = tk.Tk()
                root.withdraw()  # Hide main window
                messagebox.showerror("FFmpeg Required", error_msg)
                root.destroy()
            except:
                print(error_msg)
            
            return False
    except ImportError:
        pass  # ffmpeg_utils not available, skip check
    
    missing_modules = []
    
    for module_name, display_name in required_modules:
        try:
            __import__(module_name)
        except ImportError:
            missing_modules.append(display_name)
    
    if missing_modules:
        error_msg = (
            "Missing required dependencies:\n\n" +
            "\n".join(f"• {module}" for module in missing_modules) +
            "\n\nPlease install missing dependencies with:\n" +
            "pip install -r requirements.txt"
        )
        
        # Try to show GUI error if tkinter is available
        try:
            root = tk.Tk()
            root.withdraw()  # Hide main window
            messagebox.showerror("Missing Dependencies", error_msg)
            root.destroy()
        except:
            print(error_msg)
        
        return False
    
    return True


def check_system_requirements() -> bool:
    """Check system requirements for the application.
    
    Returns:
        True if system meets requirements, False otherwise
    """
    warnings = []
    
    # Check Python version
    if sys.version_info < (3, 8):
        warnings.append("Python 3.8 or higher is recommended for best performance.")
    
    # Check available memory (basic check)
    try:
        import psutil
        available_memory_gb = psutil.virtual_memory().available / (1024**3)
        if available_memory_gb < 4:
            warnings.append(f"Low available memory ({available_memory_gb:.1f}GB). Large video files may cause issues.")
    except ImportError:
        pass  # psutil not available, skip memory check
    
    # Check disk space in current directory
    try:
        import shutil
        free_space_gb = shutil.disk_usage('.').free / (1024**3)
        if free_space_gb < 2:
            warnings.append(f"Low disk space ({free_space_gb:.1f}GB). Video processing requires temporary storage.")
    except:
        pass  # Skip disk space check if it fails
    
    if warnings:
        warning_msg = "System Warnings:\n\n" + "\n".join(f"• {warning}" for warning in warnings)
        logging.warning(warning_msg)
        
        # Show warnings but don't prevent startup
        try:
            root = tk.Tk()
            root.withdraw()
            result = messagebox.askquestion(
                "System Warnings", 
                warning_msg + "\n\nDo you want to continue anyway?",
                icon='warning'
            )
            root.destroy()
            return result == 'yes'
        except:
            print(warning_msg)
            return True  # Continue if GUI warning fails
    
    return True


def create_default_directories() -> None:
    """Create default directories for the application."""
    directories = [
        "logs",
        "temp",
        "output",
        "backups"
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        logging.info(f"Created directory: {directory}")


def cleanup_temp_files() -> None:
    """Clean up temporary files from previous runs."""
    temp_dir = Path("temp")
    if temp_dir.exists():
        try:
            for temp_file in temp_dir.glob("*"):
                if temp_file.is_file():
                    temp_file.unlink()
                    logging.info(f"Cleaned up temp file: {temp_file}")
        except Exception as e:
            logging.warning(f"Error cleaning temp files: {e}")


def initialize_services() -> tuple:
    """Initialize application services.
    
    Returns:
        Tuple of (transcript_service, video_service, filler_detector)
    """
    logging.info("Initializing application services...")
    
    # Initialize services
    transcript_service = TranscriptService()
    video_service = VideoService()
    filler_detector = FillerWordDetector()
    
    logging.info("Services initialized successfully")
    return transcript_service, video_service, filler_detector


def main() -> None:
    """Main application entry point."""
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="VideoTextCut")
    parser.add_argument(
        "--log-level", 
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level (default: INFO)"
    )
    parser.add_argument(
        "--video-file",
        help="Video file to open on startup"
    )
    parser.add_argument(
        "--skip-checks",
        action="store_true",
        help="Skip dependency and system requirement checks"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    logging.info("Starting VideoTextCut...")
    
    try:
        # Check dependencies and system requirements
        if not args.skip_checks:
            if not check_dependencies():
                sys.exit(1)
            
            if not check_system_requirements():
                logging.info("User chose not to continue due to system warnings")
                sys.exit(0)
        
        # Create necessary directories
        create_default_directories()
        
        # Clean up temporary files
        cleanup_temp_files()
        
        # Initialize services
        transcript_service, video_service, filler_detector = initialize_services()
        
        # Create and configure the main application window
        root = tk.Tk()
        
        # Set application icon if available
        try:
            # You can add an icon file here if desired
            # root.iconbitmap('icon.ico')
            pass
        except:
            pass  # Icon not available, continue without it
        
        # Create the main application
        app = VideoTranscriptApp(root)
        
        # Open video file if specified
        if args.video_file:
            video_path = Path(args.video_file)
            if video_path.exists():
                # Schedule file opening after GUI is ready
                root.after(100, lambda: app.open_video_file(str(video_path)))
            else:
                logging.warning(f"Specified video file not found: {args.video_file}")
        
        # Setup cleanup on exit
        def on_closing():
            """Handle application closing."""
            logging.info("Application closing...")
            
            # Cancel any running operations
            tracker = get_global_tracker()
            active_ops = tracker.get_active_operations()
            for op_id in active_ops:
                tracker.cancel_operation(op_id)
                logging.info(f"Cancelled operation: {op_id}")
            
            # Clean up temporary files
            cleanup_temp_files()
            
            # Close the application
            root.quit()
            root.destroy()
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        # Start the GUI event loop
        logging.info("Starting GUI...")
        root.mainloop()
        
    except KeyboardInterrupt:
        logging.info("Application interrupted by user")
        sys.exit(0)
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        logging.error(error_msg, exc_info=True)
        
        # Try to show error dialog
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Application Error", error_msg)
            root.destroy()
        except:
            print(error_msg)
        
        sys.exit(1)
    
    logging.info("Application closed successfully")


if __name__ == "__main__":
    main()