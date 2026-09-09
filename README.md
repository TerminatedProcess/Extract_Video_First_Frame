# Extract Video First Frame

Extracts the first frame of every video in a directory tree and saves it as a PNG — or, with an interval, walks the whole video and pulls a frame every N. Useful for building thumbnails, contact sheets, wallpaper stills, or training datasets from a folder of clips.

## Features

- 🎥 MP4, AVI, MOV, MKV, WebM out of the box, and any other extension via `--ext`
- 🔄 Recursive, and **mirrors the source folder structure** so same-named videos in different subfolders never overwrite each other
- 🎞️ **Interval mode** — first frame, skip N, next frame, to the end of the video
- ⚡ Runs several ffmpeg jobs in parallel, one decode pass per video
- 🔁 Safe to re-run: work already done is skipped, so you can point it at a growing folder
- 🧱 Atomic writes — an interrupted run never leaves a half-written PNG or a partial frame set
- 🕐 `--time` to skip past videos that open on a black frame
- 📊 Summary with a list of anything that failed
- 🐍 Standard library only, no pip dependencies

## Prerequisites

- Python 3.10 or newer (3.12 recommended)
- ffmpeg

```bash
sudo pacman -S ffmpeg          # Arch / CachyOS
sudo apt install ffmpeg        # Debian / Ubuntu
brew install ffmpeg            # macOS
```

There is nothing to `pip install`. `requirements.txt` is intentionally empty.

## Usage

```bash
python extract_frames.py INPUT_DIR OUTPUT_DIR              # first frame only
python extract_frames.py INPUT_DIR OUTPUT_DIR INTERVAL     # every INTERVAL+1 frames
python extract_frames.py INPUT_DIR --beside
```

### Interval

The optional third argument is how many frames to **skip between** the ones you keep.

- **Omitted** → one PNG per video, the first frame, named `clip.png`
- **`5`** → keep frame 0, skip 5, keep frame 6, skip 5, keep frame 12 … to the end
- **`0`** → keep every frame

In interval mode the output is numbered per video: `clip_000001.png`, `clip_000002.png`, and so on, counting the frames that were kept rather than their position in the source.

A 20-frame video gives 4 PNGs at interval 5 (frames 0, 6, 12, 18), 10 at interval 1, and 20 at interval 0.

Be aware how fast this adds up: a 2-minute 30 fps clip at interval 5 is 600 PNGs.

### Options

| Option | Effect |
|---|---|
| `-I, --interval N` | Same as the third positional argument. Required instead of the positional when using `--beside` |
| `--beside` | Write PNGs next to the video instead of into an output directory |
| `--flat` | Put every PNG directly in `OUTPUT_DIR` instead of mirroring the tree |
| `-t, --time SPEC` | Start at `SPEC` (`3`, `00:00:03`) instead of the beginning |
| `-e, --ext LIST` | Extensions to match, comma separated (default `.mp4,.avi,.mov,.mkv,.webm`) |
| `-j, --jobs N` | Parallel ffmpeg jobs (default: a quarter of your cores, capped at 8) |
| `-f, --force` | Re-extract even when the PNG already exists |
| `-n, --dry-run` | Show what would be written, then stop |
| `-q, --quiet` | Only print warnings, failures and the summary |

### Examples

```bash
# Mirror a video tree into a thumbnail tree
python extract_frames.py ~/wall/wallvids ~/wall/wallfirstframe

# Every 6th frame of every video (keep one, skip five)
python extract_frames.py ~/wall/wallvids ~/wall/wallfirstframe 5

# Thumbnails alongside the videos themselves
python extract_frames.py ~/Videos --beside

# One frame per second from 30 fps footage, written next to each video
python extract_frames.py ~/Videos --beside --interval 29

# Two seconds in, overwriting what's already there, only mp4 and mkv
python extract_frames.py ~/Videos out/ --time 00:00:02 --force --ext mp4,mkv

# See what it would do first
python extract_frames.py ~/Videos out/ 5 --dry-run
```

### Example output

```
Extracting every 6 frame(s), skipping 5 from 4 video(s) into /tmp/out, 8 parallel job(s)...
FAIL  /tmp/src/b/broken.mp4
      [in#0 @ 0x55dbdd020e00] moov atom not found
ok    /tmp/out/a/clip_*.png  (4 frames)
ok    /tmp/out/b/c/clip_*.png  (12 frames)
skip  /tmp/out/b/other_*.png

============================================================
2 video(s) processed, 1 skipped (already present), 1 failed
16 frame(s) written
Failed files (1):
  - /tmp/src/b/broken.mp4
```

Exit status is `0` when everything worked and `1` if anything failed, so it drops straight into a script or a cron job.

## Output layout

By default the output mirrors the input:

```
input/                          output/
├── holiday/                    ├── holiday/
│   └── clip.mp4        →       │   └── clip.png
└── work/                       └── work/
    └── clip.mp4                    └── clip.png
```

With `--flat`, both of those become `output/clip.png` and one of them wins. The tool warns loudly and names the videos involved when this would happen — it does not silently drop one.

In interval mode the same layout holds, with each video's frames numbered beneath it:

```
output/
├── holiday/
│   ├── clip_000001.png
│   ├── clip_000002.png
│   └── clip_000003.png
└── work/
    ├── clip_000001.png
    └── clip_000002.png
```

## Notes

- **Why ffmpeg and not OpenCV.** OpenCV's `VideoCapture` returns an empty frame on a lot of real-world files (variable frame rate, unusual codecs, slight corruption) without saying why. ffmpeg either produces the frame or explains itself on stderr, and that message is passed straight through to you.
- **Case-insensitive matching.** `.MP4` from a phone or camera is matched just like `.mp4`.
- **Audio-only files are reported as failures**, not silent successes. ffmpeg exits `0` on an `.mp4` with no video stream while writing nothing, so the output is size-checked as well.
- **Atomic writes.** Each frame is written to a temporary file *in the destination directory* and then renamed into place. Staging in `/tmp` instead would cross a filesystem boundary, which turns the rename into a non-atomic copy and pays for the bytes twice. In interval mode the whole frame set is staged in a temporary directory and moved in only once ffmpeg has succeeded, so a failed run leaves nothing behind rather than a partial set.
- **One decode pass per video.** Interval mode uses ffmpeg's `select` filter to drop the frames you don't want mid-decode. Pulling frames one at a time would re-seek and re-decode the file for every image.
- **Interval re-runs are skipped as a unit.** A video is considered done if its `_000001.png` exists. `--force` re-extracts and clears any leftovers first, so widening the interval doesn't leave stale frames from the previous, denser run.

## Fish shell integration

`.salias` defines a `run` function wired to a fixed input and output directory:

```fish
set -gx IN_DIR         /home/dev/wall/wallvids
set -gx OUT_DIR        /home/dev/wall/wallfirstframe
set -gx INTERVAL_SKIP  5
```

```bash
run   # uv run extract_frames.py $IN_DIR $OUT_DIR $INTERVAL_SKIP
```

Clear `INTERVAL_SKIP` and `run` falls back to one first frame per video.

## Troubleshooting

**`ffmpeg not found`** — install it with your package manager (see Prerequisites).

**No video files found** — check the path, and remember the default extension list. Use `--ext` for anything else.

**A frame came out black** — the video genuinely opens on a black frame. Use `--time 00:00:02 --force`.

**Nothing happens on a re-run** — that is the skip behaviour working. Use `--force` to redo them.

## License

MIT — see [LICENSE](LICENSE).
