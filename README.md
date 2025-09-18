# VideoTextCut

A Python application that automatically generates transcripts from video files, detects and removes filler words, and creates trimmed video outputs. Built with Tkinter GUI, OpenAI Whisper for speech recognition, and MoviePy for video processing.

## Features

- **Automatic Transcript Generation**: Uses OpenAI Whisper for accurate speech-to-text conversion
- **Filler Word Detection**: Automatically identifies and marks filler words (um, uh, like, etc.)
- **Video Trimming**: Creates trimmed videos by removing filler segments
- **Interactive GUI**: User-friendly Tkinter interface for easy operation
- **Progress Tracking**: Real-time progress updates for long-running operations
- **Multiple Format Support**: Supports various video and audio formats
- **Customizable Settings**: Configurable Whisper models and detection parameters

## Requirements

- Python 3.8 or higher
- **FFmpeg (REQUIRED for video/audio processing)**
- At least 4GB RAM (8GB recommended for larger videos)
- GPU support optional but recommended for faster transcription

⚠️ **IMPORTANT**: FFmpeg must be installed separately and accessible from your system PATH. The application will not work without it.

## Installation

### 1. Clone or Download

Download all the application files to a directory (e.g., `videotextcut`).

### 2. Install Python Dependencies

```bash
cd videotextcut
pip install -r requirements.txt
```

### 3. Install FFmpeg (REQUIRED)

FFmpeg is essential for video processing. Choose one of the following methods:

**Windows (Choose one option):**

*Option 1 - Using Chocolatey (Recommended):*
1. Install Chocolatey from https://chocolatey.org/install
2. Open PowerShell as Administrator
3. Run: `choco install ffmpeg`

*Option 2 - Using Scoop:*
1. Install Scoop from https://scoop.sh/
2. Run: `scoop install ffmpeg`

*Option 3 - Manual Installation:*
1. Download FFmpeg from https://ffmpeg.org/download.html
2. Extract to a folder (e.g., `C:\ffmpeg`)
3. Add `C:\ffmpeg\bin` to your system PATH
4. Restart your command prompt/application

**macOS:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# CentOS/RHEL/Fedora
sudo dnf install ffmpeg

# Arch Linux
sudo pacman -S ffmpeg
```

### 4. Verify Installation

Run the test suite to ensure everything is working:

```bash
python test_app.py
```

## Usage

### Starting the Application

```bash
python main.py
```

### Basic Workflow

1. **Select Video File**: Click "Browse" to select your video file
2. **Generate Transcript**: Click "Generate Transcript" and wait for processing
3. **Review Transcript**: The transcript will appear in the text area
4. **Detect Fillers**: Click "Detect Fillers" to automatically identify filler words
5. **Edit if Needed**: Manually edit the transcript or filler detection
6. **Trim Video**: Click "Trim Video" to create the final output

### Supported Formats

**Video:** .mp4, .avi, .mov, .mkv, .wmv, .flv, .webm
**Audio:** .wav, .mp3, .m4a, .flac, .aac

## Configuration

### Whisper Models

The application supports different Whisper models with varying accuracy and speed:

- `tiny`: Fastest, least accurate (~39 MB)
- `base`: Good balance (~74 MB) - **Default**
- `small`: Better accuracy (~244 MB)
- `medium`: High accuracy (~769 MB)
- `large`: Best accuracy (~1550 MB)

To change the model, edit `models.py`:

```python
class AppConfig:
    whisper_model: str = 'small'  # Change this
```

### Custom Filler Words

You can add custom filler words by modifying `filler_detector.py`:

```python
DEFAULT_FILLER_WORDS = [
    'um', 'uh', 'like', 'you know', 'basically',
    'actually', 'literally', 'so', 'well',
    'your_custom_word'  # Add here
]
```

## File Structure

```
videotextcut/
├── main.py                 # Application entry point
├── gui.py                  # Tkinter GUI implementation
├── models.py               # Data models and configuration
├── transcript_service.py   # Whisper integration
├── video_service.py        # MoviePy video processing
├── filler_detector.py      # Filler word detection
├── progress_tracker.py     # Progress tracking system
├── test_app.py            # Test suite
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Troubleshooting

### Common Issues

**1. "WinError 2: The system cannot find the file specified" or "FFmpeg not found"**
- This means FFmpeg is not installed or not in your system PATH
- Install FFmpeg using one of the methods above
- Test installation with: `ffmpeg -version`
- Restart your terminal/command prompt after installation
- Restart the application after installing FFmpeg

**2. "CUDA out of memory" error**
- Use a smaller Whisper model (e.g., 'base' instead of 'large')
- Process shorter video segments
- Close other GPU-intensive applications

**3. Slow transcription**
- Use GPU acceleration if available
- Try a smaller Whisper model
- Process shorter video files

**4. Poor transcript quality**
- Use a larger Whisper model ('medium' or 'large')
- Ensure good audio quality in source video
- Check for background noise

**5. GUI not responding**
- Long operations run in background threads
- Check the progress dialog for updates
- Be patient with large files

### Performance Tips

- **GPU Acceleration**: Install PyTorch with CUDA support for faster processing
- **Memory Management**: Close other applications when processing large videos
- **File Size**: Consider splitting very large videos (>1GB) into smaller segments
- **Audio Quality**: Higher quality audio produces better transcripts

## Advanced Usage

### Command Line Arguments

```bash
python main.py --model large --input video.mp4 --output trimmed_video.mp4
```

### Batch Processing

For processing multiple files, you can modify `main.py` or create a custom script using the service classes:

```python
from transcript_service import TranscriptService
from video_service import VideoService
from filler_detector import FillerWordDetector

# Initialize services
transcript_service = TranscriptService()
video_service = VideoService()
detector = FillerWordDetector()

# Process video
transcript_data = transcript_service.generate_transcript('input.mp4')
detector.detect_filler_words(transcript_data)
video_service.trim_video_by_transcript('input.mp4', transcript_data, 'output.mp4')
```

### Integration with Other Tools

The modular design allows easy integration with other applications:

- Use `TranscriptService` for standalone transcription
- Use `FillerWordDetector` for text analysis
- Use `VideoService` for video processing tasks

## Contributing

To contribute to this project:

1. Run the test suite: `python test_app.py`
2. Follow the existing code style
3. Add tests for new features
4. Update documentation as needed

## License

This project is open source. Feel free to modify and distribute according to your needs.

## Acknowledgments

- **OpenAI Whisper**: For excellent speech recognition
- **MoviePy**: For video processing capabilities
- **Tkinter**: For the GUI framework
- **FFmpeg**: For multimedia processing

## Support

For issues and questions:

1. Check the troubleshooting section above
2. Run the test suite to identify problems
3. Check the console output for error messages
4. Ensure all dependencies are properly installed

---

**Happy video editing!** 🎬✂️