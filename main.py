#!/usr/bin/env python3
"""
CLI entry point.

Usage:
  python main.py "Future of AI Agents in 2026"
  python main.py "Black Holes" --language Tamil --style Motivational
  python main.py "Crypto 2026" --language English --audience professionals --auto
"""
import argparse, json, sys, time
from pathlib import Path


def print_banner():
    print("""
╔══════════════════════════════════════════════════════╗
║          🎬  YouTube AI Agent  v1.0                 ║
║   Research → Script → Voice → Visual → Edit → Done  ║
╚══════════════════════════════════════════════════════╝
""")


def main():
    parser = argparse.ArgumentParser(description="YouTube AI Video Generator")
    parser.add_argument("topic", nargs="?",
                        default="Future of AI Agents in 2026",
                        help="Video topic")
    parser.add_argument("--language", "-l", default="English",
                        choices=["English","Tamil","Hindi","Telugu","Spanish",
                                 "French","German","Arabic","Japanese","Chinese","Portuguese"])
    parser.add_argument("--style", "-s", default="Educational",
                        choices=["Educational","Cinematic","Motivational","Documentary","Storytelling"])
    parser.add_argument("--audience", "-a", default="general",
                        choices=["general","students","professionals","entrepreneurs","tech enthusiasts"])
    parser.add_argument("--auto", action="store_true",
                        help="Skip human-in-the-loop approval")
    parser.add_argument("--job-id", default=None,
                        help="Specify custom job ID")
    args = parser.parse_args()

    print_banner()
    print(f"📌 Topic:    {args.topic}")
    print(f"🌍 Language: {args.language}")
    print(f"🎭 Style:    {args.style}")
    print(f"👥 Audience: {args.audience}")
    print(f"🤖 Mode:     {'auto (no approval)' if args.auto else 'interactive'}")
    print("─" * 54)

    start = time.time()

    try:
        from graph.workflow import run_pipeline
        mode = "auto" if args.auto else "cli"
        state = run_pipeline(
            topic    = args.topic,
            language = args.language,
            style    = args.style,
            audience = args.audience,
            mode     = mode,
            job_id   = args.job_id,
        )
    except ImportError as e:
        print(f"\n❌ Import error: {e}")
        print("   Run:  pip install -r requirements.txt")
        sys.exit(1)
    except RuntimeError as e:
        print(f"\n❌ {e}")
        sys.exit(1)

    elapsed = time.time() - start

    # Print results
    print("\n" + "═" * 54)
    status = state.get("status", "unknown")
    icon   = "✅" if status == "done" else ("⏳" if status == "waiting_approval" else "❌")
    print(f"\n{icon} Status: {status.upper()}")
    print(f"⏱️  Time:   {elapsed:.0f}s ({elapsed/60:.1f} min)")

    meta = state.get("metadata", {})
    if meta.get("title"):
        print(f"\n📌 Title: {meta['title']}")
    if meta.get("tags"):
        print(f"🏷️  Tags:  {', '.join(meta['tags'][:8])}")

    qa = state.get("qa_report", {})
    if qa.get("score") is not None:
        print(f"✅ QA Score: {qa['score']}/100 (Grade: {qa.get('grade','?')})")

    print("\n📁 Output files:")
    for key, label in [
        ("video_path",     "🎬 Video     "),
        ("thumbnail_path", "🖼️  Thumbnail "),
    ]:
        path = state.get(key, "")
        if path and Path(path).exists():
            size = Path(path).stat().st_size / (1024*1024)
            print(f"   {label}: {path}  ({size:.1f}MB)")

    from config import OUTPUTS_DIR
    job_id = state.get("job_id", "")
    for label, path in [
        ("📝 Script    ", OUTPUTS_DIR / "scripts"  / f"{job_id}.json"),
        ("🏷️  Metadata  ", OUTPUTS_DIR / "metadata" / f"{job_id}.json"),
    ]:
        if path.exists():
            print(f"   {label}: {path}")

    if state.get("errors"):
        print("\n⚠️  Errors:")
        for err in state["errors"]:
            print(f"   • {err[:100]}")

    print("\n" + "═" * 54)

    if meta.get("description"):
        print("\n📋 YouTube Description (first 300 chars):")
        print(meta["description"][:300])

    print("\n✨ Done! Your YouTube video is ready.\n")


if __name__ == "__main__":
    main()
