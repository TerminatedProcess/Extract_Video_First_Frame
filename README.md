# Extract Video First Frame

A Python utility that extracts the first frame from video files in a directory and saves them as PNG images. This tool is useful for creating thumbnails or previews from a collection of videos.

## Features

- 🎥 Supports multiple video formats (MP4, AVI, MOV, MKV, WebM)
- 🔄 Recursive directory scanning
- ⚡ Uses ffmpeg for robust video processing
- 📊 Processing summary statistics
- 🔒 Error handling and validation
- 📁 Separate output directory for organized frame storage

## Prerequisites

- Python 3.6 or higher
- ffmpeg (must be installed on your system)

### Installing ffmpeg

**Linux (Debian/Ubuntu):**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Linux (Arch/Garuda):**
```bash
sudo pacman -S ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
Download from [ffmpeg.org](https://ffmpeg.org/download.html) or use:
```bash
winget install ffmpeg
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/Extract_Video_First_Frame.git
cd Extract_Video_First_Frame
```

2. (Optional but recommended) Create and activate a virtual environment:
```bash
python -m venv .venv

# On Windows
.venv\Scripts\activate

# On macOS/Linux
source .venv/bin/activate
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Command

```bash
python extract_frames.py <input_dir> <output_dir>
```

### Examples

Extract frames from videos in `videos/` directory and save to `frames/`:
```bash
python extract_frames.py videos/ frames/
```

Using absolute paths:
```bash
python extract_frames.py /path/to/videos /path/to/output
```

### What It Does

1. Recursively scans the input directory for video files
2. Extracts the first frame from each video using ffmpeg
3. Saves frames as high-quality PNG files in the output directory
4. Names output files using the video's filename (e.g., `video.mp4` → `video.png`)
5. Provides a summary of successful and failed extractions

### Example Output

```
Found 5 video files.
✓ Saved frame to output/video1.png
✓ Saved frame to output/video2.png
✗ Failed to extract frame from corrupted_video.mp4
  Error: Invalid data found when processing input
✓ Saved frame to output/video3.png
✓ Saved frame to output/video4.png

============================================================
Summary: 4/5 frames extracted successfully
Failed files (1):
  - corrupted_video.mp4
```

## Supported Video Formats

- MP4 (`.mp4`)
- AVI (`.avi`)
- MOV (`.mov`)
- MKV (`.mkv`)
- WebM (`.webm`)

## Error Handling

The script handles common issues gracefully:
- Missing or invalid directories
- Corrupted video files
- Unsupported video encodings
- Missing ffmpeg installation
- Insufficient permissions

All errors are reported with descriptive messages to help troubleshoot issues.

## Project Structure

```
Extract_Video_First_Frame/
├── extract_frames.py      # Main script
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── input/                # Default input directory (optional)
└── output/               # Default output directory (optional)
```

## Troubleshooting

**"ffmpeg: command not found"**
- Install ffmpeg using the instructions in the Prerequisites section

**No video files found**
- Check that your input directory contains videos with supported extensions
- Verify the path to your input directory is correct

**Failed to extract frame**
- The video file may be corrupted
- The video codec may not be supported by ffmpeg
- Try re-encoding the video with a standard codec

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

This means you are free to use, modify, and distribute this software for personal or commercial purposes, with attribution.

## Support

If you encounter any issues or have questions:
1. Check the Troubleshooting section above
2. Review existing issues in the GitHub repository
3. Create a new issue with a detailed description of your problem
4. Include any error messages and your environment details (OS, Python version, ffmpeg version)
