#!/usr/bin/env python3
"""
Demo Launcher - Easy access to presentation-friendly demos

This script provides an easy way to launch different demo modes:
1. Interactive Presentation Demo - Full control for live presentations
2. Database Inspector - Show actual database states
3. Quick Demo - 15-minute version
4. Auto Demo - For testing purposes

Perfect for presenters who need quick access to the right demo mode.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def print_banner():
    """Print demo launcher banner"""
    print("=" * 80)
    print("ENTITY RESOLUTION DEMO LAUNCHER".center(80))
    print("=" * 80)
    print()
    print("[DEMO] Choose your demo experience:")
    print()


def print_demo_options():
    """Print available demo options"""
    print("1. [PRESENTATION] Interactive Presentation Demo")
    print("   Perfect for live presentations with manual control")
    print("   Features: Step-by-step, explanations, before/after views")
    print("   Duration: 45-60 minutes")
    print()
    
    print("2. [INSPECT] Database Inspector")
    print("   Show actual database states during presentations")
    print("   Features: Real-time data views, before/after comparisons")
    print("   Duration: As needed")
    print()
    
    print("3. [QUICK] Quick Demo")
    print("   Fast-paced demo for time-constrained presentations")
    print("   Features: Key highlights only, auto-advancing")
    print("   Duration: 15-20 minutes")
    print()
    
    print("4. [AUTO] Auto Demo")
    print("   Automated demo for testing and practice")
    print("   Features: No manual intervention, full pipeline")
    print("   Duration: 5-10 minutes")
    print()
    
    print("5. [DOCS] View Presentation Script")
    print("   Open the comprehensive presentation guide")
    print()
    
    print("6. [CHECK] Environment Check")
    print("   Verify all demo components are working")
    print()
    
    print("q. Quit")
    print()


def launch_interactive_demo():
    """Launch the interactive presentation demo"""
    print("[PRESENTATION] Launching Interactive Presentation Demo...")
    print("This demo gives you full control over pacing and explanations.")
    print()
    
    scripts_dir = Path(__file__).parent / "scripts"
    demo_script = scripts_dir / "interactive_presentation_demo.py"
    
    if demo_script.exists():
        os.system(f"cd {project_root} && python {demo_script}")
    else:
        print("[ERROR] Interactive demo script not found!")
        print(f"Expected: {demo_script}")


def launch_database_inspector():
    """Launch the database inspector"""
    print("[INSPECT] Launching Database Inspector...")
    print("Use this to show actual database states during your presentation.")
    print()
    
    scripts_dir = Path(__file__).parent / "scripts"
    inspector_script = scripts_dir / "database_inspector.py"
    
    if inspector_script.exists():
        os.system(f"cd {project_root} && python {inspector_script}")
    else:
        print("[ERROR] Database inspector script not found!")
        print(f"Expected: {inspector_script}")


def launch_quick_demo():
    """Launch quick demo with auto-advance"""
    print("[QUICK] Launching Quick Demo...")
    print("This is a fast-paced version perfect for short presentations.")
    print()
    
    scripts_dir = Path(__file__).parent / "scripts"
    demo_script = scripts_dir / "interactive_presentation_demo.py"
    
    if demo_script.exists():
        # Set auto mode for quick demo
        print("Running in auto mode with 2-second delays...")
        print("Press Ctrl+C to interrupt if needed.")
        print()
        
        # Import and run with auto mode
        sys.path.insert(0, str(scripts_dir))
        try:
            from interactive_presentation_demo import InteractivePresentationDemo
            
            demo = InteractivePresentationDemo()
            demo.auto_mode = True
            demo.run_presentation_demo()
            
        except ImportError:
            print("[ERROR] Could not import interactive demo. Running as subprocess...")
            os.system(f"cd {project_root} && python {demo_script}")
    else:
        print("[ERROR] Demo script not found!")


def launch_auto_demo():
    """Launch the automated demo"""
    print("[AUTO] Launching Automated Demo...")
    print("This runs the complete pipeline automatically for testing.")
    print()
    
    # Use the original demo orchestrator in auto mode
    scripts_dir = Path(__file__).parent / "scripts"
    auto_script = scripts_dir / "demo_orchestrator.py"
    
    if auto_script.exists():
        os.system(f"cd {project_root} && python {auto_script} --auto --records 1000")
    else:
        print("[ERROR] Auto demo script not found!")


def view_presentation_script():
    """Open the presentation script"""
    print("[DOCS] Opening Presentation Script...")
    
    script_file = Path(__file__).parent / "PRESENTATION_SCRIPT.md"
    
    if script_file.exists():
        # Try to open in default editor
        if sys.platform == "darwin":  # macOS
            os.system(f"open {script_file}")
        elif sys.platform == "linux":
            os.system(f"xdg-open {script_file}")
        elif sys.platform == "win32":
            os.system(f"start {script_file}")
        else:
            print(f"Presentation script location: {script_file}")
            print("Please open this file in your preferred editor.")
    else:
        print("[ERROR] Presentation script not found!")


def environment_check():
    """Check if all demo components are available"""
    print("[CHECK] Checking Demo Environment...")
    print()
    
    # Check Python version
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    print(f"Python version: {python_version}")
    
    # Check required files
    required_files = [
        "demo/scripts/interactive_presentation_demo.py",
        "demo/scripts/database_inspector.py",
        "demo/scripts/demo_orchestrator.py",
        "demo/PRESENTATION_SCRIPT.md"
    ]
    
    all_good = True
    
    print("\n[FILES] Required Files:")
    for file_path in required_files:
        full_path = project_root / file_path
        if full_path.exists():
            print(f"  [OK] {file_path}")
        else:
            print(f"  [MISSING] {file_path}")
            all_good = False
    
    # Check required packages
    print("\n[PACKAGES] Required Packages:")
    required_packages = ["arango"]
    optional_packages = ["tabulate"]
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"  [OK] {package}")
        except ImportError:
            print(f"  [MISSING] {package} (install with: pip install {package})")
            all_good = False
    
    print("\n[PACKAGES] Optional Packages (for enhanced formatting):")
    for package in optional_packages:
        try:
            __import__(package)
            print(f"  [OK] {package}")
        except ImportError:
            print(f"  [OPTIONAL] {package} (install with: pip install {package} for better tables)")
    
    # Check database connection (optional)
    print("\n[DATABASE] Database Connection:")
    try:
        from src.entity_resolution.utils.config import get_config
        config = get_config()
        print(f"  [INFO] Host: {config.db.host}:{config.db.port}")
        print(f"  [INFO] Database: {config.db.database}")
        print("  [INFO] Connection test skipped (run demo to verify)")
    except Exception as e:
        print(f"  [ERROR] Configuration error: {e}")
        all_good = False
    
    print()
    if all_good:
        print("[SUCCESS] Environment check passed! All demos should work.")
    else:
        print("[WARNING] Environment issues detected. Some demos may not work.")
        print("   Please install missing packages or check file paths.")


def main():
    """Main demo launcher"""
    
    print_banner()
    
    while True:
        print_demo_options()
        
        choice = input("Enter your choice (1-6 or q): ").strip().lower()
        
        if choice == 'q':
            print("Goodbye! Happy presenting!")
            break
        elif choice == '1':
            launch_interactive_demo()
        elif choice == '2':
            launch_database_inspector()
        elif choice == '3':
            launch_quick_demo()
        elif choice == '4':
            launch_auto_demo()
        elif choice == '5':
            view_presentation_script()
        elif choice == '6':
            environment_check()
        else:
            print("[ERROR] Invalid choice. Please enter 1-6 or q.")
        
        print("\n" + "-" * 80 + "\n")


if __name__ == "__main__":
    main()
