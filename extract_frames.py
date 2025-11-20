import argparse
import subprocess
import sys
from pathlib import Path

def extract_frames(input_dir, output_dir):
    """
    Extract first frame from videos using ffmpeg instead of OpenCV.
    This is more robust for videos with encoding issues.
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)

    # Video extensions to look for
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}

    # Recursively find all video files
    video_files = []
    for ext in video_extensions:
        video_files.extend(input_path.rglob(f'*{ext}'))

    if not video_files:
        print(f"No video files found in {input_dir}")
        return

    print(f"Found {len(video_files)} video files.")

    success_count = 0
    failed_files = []

    for video_file in sorted(video_files):
        try:
            # Construct output filename
            output_filename = output_path / f"{video_file.stem}.png"

            # Use ffmpeg to extract the first frame
            # -i: input file
            # -vframes 1: extract only 1 frame
            # -q:v 2: high quality (scale 2-31, lower is better)
            # -update 1: allows single image output
            cmd = [
                'ffmpeg',
                '-i', str(video_file),
                '-vframes', '1',
                '-q:v', '2',
                '-update', '1',
                '-y',  # Overwrite output file
                str(output_filename)
            ]

            # Run ffmpeg with suppressed output (unless there's an error)
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if result.returncode == 0 and output_filename.exists():
                print(f"✓ Saved frame to {output_filename}")
                success_count += 1
            else:
                print(f"✗ Failed to extract frame from {video_file}")
                failed_files.append(video_file.name)
                if result.stderr:
                    # Print first line of error
                    error_lines = result.stderr.split('\n')
                    for line in error_lines:
                        if 'error' in line.lower() or 'invalid' in line.lower():
                            print(f"  Error: {line.strip()}")
                            break

        except Exception as e:
            print(f"✗ Error processing {video_file}: {e}")
            failed_files.append(video_file.name)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Summary: {success_count}/{len(video_files)} frames extracted successfully")
    if failed_files:
        print(f"Failed files ({len(failed_files)}):")
        for f in failed_files:
            print(f"  - {f}")
def main():
    parser = argparse.ArgumentParser(description="Recursively extract first frame from video files.")
    parser.add_argument("input_dir", help="Input directory containing video files")
    parser.add_argument("output_dir", help="Output directory to save extracted frames")
    
    args = parser.parse_args()
    
    extract_frames(args.input_dir, args.output_dir)
if __name__ == "__main__":
    main()

