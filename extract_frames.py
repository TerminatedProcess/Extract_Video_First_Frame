#!/usr/bin/env python3
"""Extract frames from every video in a tree as PNG.

By default takes just the first frame of each video. Given an interval, it
walks the whole video instead: first frame, skip N, next frame, skip N, and so
on to the end.

Uses ffmpeg rather than OpenCV: it is far more tolerant of odd codecs and
damaged files, and it is already a hard dependency of anything that works with
video on this machine. Nothing outside the standard library is needed.

  extract_frames.py INPUT_DIR OUTPUT_DIR        # first frame of each video
  extract_frames.py INPUT_DIR OUTPUT_DIR 5      # every 6th frame (skip 5)
  extract_frames.py INPUT_DIR --beside          # write next to each video
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DEFAULT_EXTS = ".mp4,.avi,.mov,.mkv,.webm"

# One lock so parallel workers cannot interleave half-written lines.
_print_lock = threading.Lock()


def log(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)


def find_videos(input_path: Path, exts: set[str]) -> list[Path]:
    """Recursively collect video files, matching extensions case-insensitively.

    rglob('*.mp4') is case-sensitive on Linux and silently misses '.MP4', which
    is a common way for phone and camera footage to be named.
    """
    return sorted(
        p for p in input_path.rglob("*")
        if p.is_file() and p.suffix.lower() in exts
    )


def plan_output(video: Path, root: Path, out_dir: Path | None, flat: bool) -> Path:
    """Decide where a video's PNG goes.

    In interval mode this is the base name: '.../clip.png' becomes the stem for
    '.../clip_000001.png', '.../clip_000002.png' and so on.
    """
    if out_dir is None:                       # --beside
        return video.with_suffix(".png")
    if flat:
        return out_dir / f"{video.stem}.png"
    rel = video.relative_to(root)             # mirror the source tree
    return out_dir / rel.with_suffix(".png")


def _ffmpeg_base(at_time: str | None) -> list[str]:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]
    if at_time:
        cmd += ["-ss", at_time]               # before -i, so the seek is fast
    return cmd


def _report_failure(video: Path, stderr: str) -> str:
    log(f"FAIL  {video}")
    for line in (stderr or "").splitlines():
        if line.strip():
            log(f"      {line.strip()}")
    return "fail"


def extract_single(video: Path, out: Path, at_time: str | None, force: bool,
                   quiet: bool) -> tuple[str, int]:
    """Extract just the first frame. Returns (outcome, frames_written)."""
    if out.exists() and not force:
        if not quiet:
            log(f"skip  {out}")
        return "skip", 0

    out.parent.mkdir(parents=True, exist_ok=True)

    # Stage in the destination directory, not /tmp. A move across filesystems
    # is a copy, so it is not atomic and it pays for the bytes twice; within
    # one directory it is a rename, which is both.
    tmp_fd, tmp_name = tempfile.mkstemp(suffix=".png", prefix=".ff_", dir=out.parent)
    os.close(tmp_fd)
    tmp_path: Path | None = Path(tmp_name)

    cmd = _ffmpeg_base(at_time) + [
        "-i", str(video), "-frames:v", "1", "-update", "1", str(tmp_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)

        # ffmpeg can exit 0 having written nothing — an .mp4 holding only an
        # audio stream does exactly that — so the size check is not redundant.
        if (result.returncode != 0 or not tmp_path.exists()
                or tmp_path.stat().st_size == 0):
            return _report_failure(video, result.stderr), 0

        os.replace(tmp_path, out)
        tmp_path = None
        if not quiet:
            log(f"ok    {out}")
        return "ok", 1

    except Exception as exc:                  # unreadable path, permissions, ...
        log(f"FAIL  {video}\n      {exc}")
        return "fail", 0

    finally:
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def extract_interval(video: Path, out_base: Path, step: int, at_time: str | None,
                     force: bool, quiet: bool) -> tuple[str, int]:
    """Extract every `step`-th frame across the whole video.

    One ffmpeg pass per video, not one per frame: the select filter keeps the
    frames we want and drops the rest while decoding exactly once. Extracting
    frame-by-frame would re-seek and re-decode for every single image.
    """
    prefix = out_base.with_suffix("")         # .../clip
    first = Path(f"{prefix}_000001.png")

    if first.exists() and not force:
        if not quiet:
            log(f"skip  {prefix}_*.png")
        return "skip", 0

    out_base.parent.mkdir(parents=True, exist_ok=True)

    # Whole-video output cannot be one atomic rename, so stage the entire set in
    # a temp directory alongside the destination and only move it into place
    # once ffmpeg has succeeded. A failed or interrupted run leaves nothing.
    staging = Path(tempfile.mkdtemp(prefix=".ff_", dir=out_base.parent))

    # The comma inside mod() must be escaped: an unescaped one would be read as
    # a separator between two filters in the chain.
    select = f"select=not(mod(n\\,{step}))"
    cmd = _ffmpeg_base(at_time) + [
        "-i", str(video),
        "-vf", select,
        "-fps_mode", "passthrough",           # keep every frame select() passes
        str(staging / "f_%06d.png"),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        produced = sorted(staging.glob("f_*.png"))

        if result.returncode != 0 or not produced:
            return _report_failure(video, result.stderr), 0

        # With --force an earlier run may have left more frames than this one
        # produces; clear them so the output set matches this run exactly.
        if force:
            for stale in sorted(prefix.parent.glob(f"{prefix.name}_*.png")):
                try:
                    stale.unlink()
                except OSError:
                    pass

        for index, frame in enumerate(produced, start=1):
            os.replace(frame, f"{prefix}_{index:06d}.png")

        if not quiet:
            log(f"ok    {prefix}_*.png  ({len(produced)} frames)")
        return "ok", len(produced)

    except Exception as exc:
        log(f"FAIL  {video}\n      {exc}")
        return "fail", 0

    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Recursively extract frames from video files as PNG.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""interval:
  With no interval, one PNG per video: clip.png (the first frame).
  With an interval of N, the first frame is kept, then N frames are skipped,
  then the next is kept, to the end of the video. So N=5 keeps frames
  0, 6, 12, 18, ... and writes clip_000001.png, clip_000002.png, ...
  N=0 keeps every frame.

examples:
  extract_frames.py ~/wall/wallvids ~/wall/wallfirstframe
  extract_frames.py ~/wall/wallvids ~/wall/wallfirstframe 5
  extract_frames.py ~/Videos --beside --interval 30
  extract_frames.py ~/Videos out/ --time 00:00:02 --force
""",
    )
    ap.add_argument("input_dir", help="Directory to scan (recursively)")
    ap.add_argument("output_dir", nargs="?",
                    help="Where PNGs go. Omit only with --beside.")
    ap.add_argument("interval", nargs="?", type=int,
                    help="Frames to skip between kept frames. Omit for "
                         "first-frame-only. With --beside use --interval "
                         "instead, since there is no OUTPUT_DIR to sit after.")
    ap.add_argument("-I", "--interval", dest="interval_opt", type=int,
                    metavar="N", help="Same as the third positional argument")
    ap.add_argument("--beside", action="store_true",
                    help="Write PNGs next to each video instead of into an "
                         "output directory")
    ap.add_argument("--flat", action="store_true",
                    help="Put every PNG directly in OUTPUT_DIR instead of "
                         "mirroring the source tree (legacy behaviour; can "
                         "collide when two subfolders hold the same filename)")
    ap.add_argument("-t", "--time", metavar="SPEC",
                    help="Start at SPEC (e.g. 3, 00:00:03) instead of the "
                         "beginning, for videos that open on black")
    ap.add_argument("-e", "--ext", default=DEFAULT_EXTS, metavar="LIST",
                    help=f"Comma-separated extensions (default: {DEFAULT_EXTS})")
    ap.add_argument("-j", "--jobs", type=int, metavar="N",
                    help="Parallel ffmpeg jobs (default: a quarter of your "
                         "cores, capped at 8)")
    ap.add_argument("-f", "--force", action="store_true",
                    help="Re-extract even if the PNGs already exist")
    ap.add_argument("-n", "--dry-run", action="store_true",
                    help="List what would be written, then stop")
    ap.add_argument("-q", "--quiet", action="store_true",
                    help="Only print warnings, failures and the summary")
    args = ap.parse_args()

    if not shutil.which("ffmpeg"):
        print("ffmpeg not found. Install it with:  sudo pacman -S ffmpeg",
              file=sys.stderr)
        return 1

    if args.interval is not None and args.interval_opt is not None:
        ap.error("give the interval once, either positionally or with --interval")
    interval = args.interval if args.interval is not None else args.interval_opt

    if interval is not None and interval < 0:
        ap.error(f"interval must be 0 or greater, got {interval}")

    if not args.beside and not args.output_dir:
        ap.error("give an OUTPUT_DIR, or use --beside to write next to each video")
    if args.beside and args.output_dir:
        ap.error("--beside takes no OUTPUT_DIR; pass the interval with --interval")

    input_path = Path(args.input_dir).expanduser().resolve()
    if not input_path.is_dir():
        print(f"Not a directory: {input_path}", file=sys.stderr)
        return 1

    out_dir = None
    if not args.beside:
        out_dir = Path(args.output_dir).expanduser().resolve()

    exts = {("." + e.strip().lstrip(".")).lower()
            for e in args.ext.split(",") if e.strip()}
    if not exts:
        print(f"--ext matched nothing usable: {args.ext}", file=sys.stderr)
        return 1

    videos = find_videos(input_path, exts)
    if not videos:
        pretty = ", ".join(sorted(exts))
        print(f"No {pretty} files found under {input_path}", file=sys.stderr)
        return 1

    jobs = args.jobs if args.jobs else min(8, max(1, (os.cpu_count() or 4) // 4))
    if jobs < 1:
        print(f"--jobs must be at least 1, got {jobs}", file=sys.stderr)
        return 1

    pairs = [(v, plan_output(v, input_path, out_dir, args.flat)) for v in videos]

    # In flat mode two videos in different subfolders can map to one name. The
    # old behaviour was to silently treat the second as "already done", which
    # looked like success. Say so instead.
    if args.flat:
        collisions: dict[Path, list[Path]] = {}
        for video, out in pairs:
            collisions.setdefault(out, []).append(video)
        for out, vs in sorted((o, v) for o, v in collisions.items() if len(v) > 1):
            print(f"WARN  {len(vs)} videos map to {out.stem}; only the first "
                  f"is kept. Drop --flat to keep them apart.", file=sys.stderr)
            for v in vs:
                print(f"        {v}", file=sys.stderr)

    step = None if interval is None else interval + 1

    if args.dry_run:
        mode = ("the first frame" if step is None
                else f"every {step} frame(s) — skipping {interval} between each")
        print(f"Would take {mode} from {len(pairs)} video(s), "
              f"{jobs} parallel job(s):")
        for video, out in pairs:
            target = out if step is None else f"{out.with_suffix('')}_NNNNNN.png"
            print(f"  {video}\n    -> {target}")
        return 0

    if not args.quiet:
        where = "beside each video" if args.beside else str(out_dir)
        mode = ("first frame" if step is None
                else f"every {step} frame(s), skipping {interval}")
        print(f"Extracting {mode} from {len(pairs)} video(s) into {where}, "
              f"{jobs} parallel job(s)...")

    tally = {"ok": 0, "skip": 0, "fail": 0}
    frames_written = 0
    failed: list[Path] = []

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        # ffmpeg does the work in its own process, so threads are only waiting
        # on it — the GIL is not in the way here.
        if step is None:
            futures = {
                pool.submit(extract_single, v, o, args.time, args.force,
                            args.quiet): v
                for v, o in pairs
            }
        else:
            futures = {
                pool.submit(extract_interval, v, o, step, args.time, args.force,
                            args.quiet): v
                for v, o in pairs
            }
        try:
            for fut, video in futures.items():
                outcome, count = fut.result()
                tally[outcome] += 1
                frames_written += count
                if outcome == "fail":
                    failed.append(video)
        except KeyboardInterrupt:
            print("\nInterrupted; cancelling remaining work.", file=sys.stderr)
            for fut in futures:
                fut.cancel()
            return 130

    print(f"\n{'=' * 60}")
    print(f"{tally['ok']} video(s) processed, {tally['skip']} skipped "
          f"(already present), {tally['fail']} failed")
    if step is not None:
        print(f"{frames_written} frame(s) written")
    if failed:
        print(f"Failed files ({len(failed)}):")
        for f in sorted(failed):
            print(f"  - {f}")

    return 1 if tally["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
