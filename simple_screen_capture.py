#!/usr/bin/env python3
"""
Simple Screen Capture Tool

A lightweight screen capture tool that uses built-in macOS tools
to avoid dependency issues with pyautogui.
"""

import argparse
import datetime
import os
import subprocess
import sys
from pathlib import Path


def capture_full_screen(output_path: Path) -> None:
    """Capture the entire screen using macOS screencapture command."""
    try:
        subprocess.run([
            "screencapture", 
            "-x",  # Don't play sound
            str(output_path)
        ], check=True)
        print(f"Full screen captured and saved to: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error capturing screen: {e}")
        sys.exit(1)


def capture_region(x: int, y: int, width: int, height: int, output_path: Path) -> None:
    """Capture a specific region using macOS screencapture command."""
    try:
        # macOS screencapture region format: x,y,width,height
        region = f"{x},{y},{width},{height}"
        subprocess.run([
            "screencapture", 
            "-x",  # Don't play sound
            "-R", region,  # Region to capture
            str(output_path)
        ], check=True)
        print(f"Region captured ({width}x{height} at {x},{y}) and saved to: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error capturing region: {e}")
        sys.exit(1)


def capture_interactive(output_path: Path) -> None:
    """Capture interactively using macOS screencapture command."""
    try:
        print("\nInteractive region selection:")
        print("1. Click and drag to select the area you want to capture")
        print("2. Release the mouse button to capture")
        print()
        
        subprocess.run([
            "screencapture", 
            "-x",  # Don't play sound
            "-i",  # Interactive mode
            str(output_path)
        ], check=True)
        print(f"Interactive capture saved to: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error during interactive capture: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCapture cancelled by user")
        sys.exit(0)


def capture_window(output_path: Path) -> None:
    """Capture a specific window using macOS screencapture command."""
    try:
        print("\nWindow capture mode:")
        print("1. Click on the window you want to capture")
        print("2. The window will be captured automatically")
        print()
        
        subprocess.run([
            "screencapture", 
            "-x",  # Don't play sound
            "-w",  # Window mode
            str(output_path)
        ], check=True)
        print(f"Window captured and saved to: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error capturing window: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCapture cancelled by user")
        sys.exit(0)


def build_default_output_path(prefix: str = "screenshot") -> Path:
    """Build default output path with timestamp."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    screenshots_dir = Path(__file__).resolve().parent / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    return screenshots_dir / f"{prefix}-{timestamp}.png"


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Simple screen capture tool using macOS built-in tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Capture full screen
  python3 simple_screen_capture.py

  # Capture specific region
  python3 simple_screen_capture.py --region 100 100 800 600

  # Interactive region selection (recommended for charts)
  python3 simple_screen_capture.py --interactive

  # Capture specific window
  python3 simple_screen_capture.py --window

  # Capture with custom output path
  python3 simple_screen_capture.py --output chart.png
        """
    )
    
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output image file path (PNG). Default: screenshots/screenshot-YYYYmmdd-HHMMSS.png"
    )
    
    parser.add_argument(
        "--region",
        nargs=4,
        type=int,
        metavar=("X", "Y", "WIDTH", "HEIGHT"),
        help="Capture specific region: X Y WIDTH HEIGHT"
    )
    
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Interactively select region to capture (recommended for charts)"
    )
    
    parser.add_argument(
        "--window", "-w",
        action="store_true",
        help="Capture specific window"
    )
    
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Delay in seconds before capturing (useful for preparing the screen)"
    )
    
    parser.add_argument(
        "--prefix",
        default="screenshot",
        help="Prefix for default filename (default: screenshot)"
    )
    
    return parser.parse_args()


def main() -> None:
    """Main function."""
    args = parse_args()
    
    # Build output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = build_default_output_path(args.prefix)
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Add delay if specified
    if args.delay > 0:
        print(f"Waiting {args.delay} seconds before capture...")
        import time
        time.sleep(args.delay)
    
    try:
        if args.region:
            # Capture specific region
            x, y, width, height = args.region
            print(f"Capturing region: {width}x{height} at ({x}, {y})")
            capture_region(x, y, width, height, output_path)
            
        elif args.interactive:
            # Interactive region selection
            print("Interactive region selection mode")
            capture_interactive(output_path)
            
        elif args.window:
            # Capture specific window
            print("Window capture mode")
            capture_window(output_path)
            
        else:
            # Capture full screen
            print("Capturing full screen...")
            capture_full_screen(output_path)
        
        print(f"Screenshot saved to: {output_path}")
        
    except KeyboardInterrupt:
        print("\nCapture cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"Error during capture: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
