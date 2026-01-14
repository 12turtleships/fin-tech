#!/usr/bin/env python3
"""
Desktop Screen Capture Tool

This script captures screenshots of your actual desktop screen, including charts,
trading applications, or any other content visible on your screen.
"""

import argparse
import datetime
import os
import time
from pathlib import Path
from typing import Optional, Tuple

try:
    from PIL import Image, ImageGrab
    from PIL.Image import Image as PILImage
except ImportError:
    print("Error: PIL (Pillow) is required. Install it with: pip install Pillow")
    exit(1)

try:
    import pyautogui
except ImportError:
    print("Error: pyautogui is required. Install it with: pip install pyautogui")
    exit(1)


def get_screen_size() -> Tuple[int, int]:
    """Get the current screen size."""
    return pyautogui.size()


def capture_full_screen(output_path: Path) -> None:
    """Capture the entire screen."""
    screenshot = ImageGrab.grab()
    screenshot.save(output_path)
    print(f"Full screen captured: {screenshot.size}")


def capture_region(x: int, y: int, width: int, height: int, output_path: Path) -> None:
    """Capture a specific region of the screen."""
    bbox = (x, y, x + width, y + height)
    screenshot = ImageGrab.grab(bbox)
    screenshot.save(output_path)
    print(f"Region captured: {screenshot.size} at ({x}, {y})")


def capture_window_by_title(window_title: str, output_path: Path) -> None:
    """Capture a specific window by its title (macOS only)."""
    try:
        import subprocess
        
        # Get window information using AppleScript
        script = f'''
        tell application "System Events"
            set windowList to every window of every process
            repeat with aWindow in windowList
                try
                    if title of aWindow contains "{window_title}" then
                        set windowPosition to position of aWindow
                        set windowSize to size of aWindow
                        return (item 1 of windowPosition) & "," & (item 2 of windowPosition) & "," & (item 1 of windowSize) & "," & (item 2 of windowSize)
                    end if
                end try
            end repeat
        end tell
        '''
        
        result = subprocess.run(['osascript', '-e', script], 
                              capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0 and result.stdout.strip():
            coords = result.stdout.strip().split(',')
            x, y, width, height = map(int, coords)
            capture_region(x, y, width, height, output_path)
        else:
            print(f"Window with title '{window_title}' not found")
            return
            
    except Exception as e:
        print(f"Error capturing window: {e}")
        return


def interactive_region_selection() -> Tuple[int, int, int, int]:
    """Allow user to interactively select a region to capture."""
    print("\nInteractive region selection:")
    print("1. Move your mouse to the top-left corner of the area you want to capture")
    print("2. Press Enter when ready...")
    input()
    
    x1, y1 = pyautogui.position()
    print(f"Top-left corner: ({x1}, {y1})")
    
    print("3. Move your mouse to the bottom-right corner of the area you want to capture")
    print("4. Press Enter when ready...")
    input()
    
    x2, y2 = pyautogui.position()
    print(f"Bottom-right corner: ({x2}, {y2})")
    
    # Ensure coordinates are in the correct order
    x = min(x1, x2)
    y = min(y1, y2)
    width = abs(x2 - x1)
    height = abs(y2 - y1)
    
    return x, y, width, height


def build_default_output_path(prefix: str = "screenshot") -> Path:
    """Build default output path with timestamp."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    screenshots_dir = Path(__file__).resolve().parent / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    return screenshots_dir / f"{prefix}-{timestamp}.png"


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Capture screenshots of your desktop screen",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Capture full screen
  python screen_capture_desktop.py

  # Capture specific region
  python screen_capture_desktop.py --region 100 100 800 600

  # Interactive region selection
  python screen_capture_desktop.py --interactive

  # Capture specific window (macOS)
  python screen_capture_desktop.py --window "Coinbase"

  # Capture with custom output path
  python screen_capture_desktop.py --output chart.png
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
        help="Interactively select region to capture"
    )
    
    parser.add_argument(
        "--window", "-w",
        help="Capture specific window by title (macOS only)"
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
        time.sleep(args.delay)
    
    # Get screen size for reference
    screen_width, screen_height = get_screen_size()
    print(f"Screen size: {screen_width}x{screen_height}")
    
    try:
        if args.region:
            # Capture specific region
            x, y, width, height = args.region
            print(f"Capturing region: {width}x{height} at ({x}, {y})")
            capture_region(x, y, width, height, output_path)
            
        elif args.interactive:
            # Interactive region selection
            x, y, width, height = interactive_region_selection()
            print(f"Capturing region: {width}x{height} at ({x}, {y})")
            capture_region(x, y, width, height, output_path)
            
        elif args.window:
            # Capture specific window
            print(f"Capturing window: {args.window}")
            capture_window_by_title(args.window, output_path)
            
        else:
            # Capture full screen
            print("Capturing full screen...")
            capture_full_screen(output_path)
        
        print(f"Screenshot saved to: {output_path}")
        
    except KeyboardInterrupt:
        print("\nCapture cancelled by user")
    except Exception as e:
        print(f"Error during capture: {e}")


if __name__ == "__main__":
    main()
