#!/usr/bin/env python3
"""
Quick Chart Capture Tool

A simple wrapper for capturing trading charts using macOS built-in tools.
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Main function for quick chart capture."""
    script_dir = Path(__file__).parent
    screen_capture_script = script_dir / "simple_screen_capture.py"
    
    # Default to interactive mode for chart capture
    args = ["python3", str(screen_capture_script), "--interactive", "--prefix", "chart"]
    
    # Add any additional arguments passed to this script
    if len(sys.argv) > 1:
        args.extend(sys.argv[1:])
    
    print("📊 Chart Capture Tool")
    print("====================")
    print("This will help you capture trading charts from your screen.")
    print("You'll be able to click and drag to select the chart area.")
    print()
    
    try:
        subprocess.run(args, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCapture cancelled by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
