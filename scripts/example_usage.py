"""
Example script showing how to use CruxCam core modules programmatically.
This demonstrates using the refactored code without the Streamlit UI.
"""
from pathlib import Path
from core.pose_analyzer import PoseAnalyzer
from core.video_processor import VideoProcessor


def main():
    """Process a video and display results."""
    
    # Configuration
    input_video = "inputs/tomoa_outside.mp4"
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)
    output_video = output_dir / "example_output.mp4"
    
    # Check if input exists
    if not Path(input_video).exists():
        print(f"Error: Input video not found: {input_video}")
        print("Please place a video file at that location or update the path.")
        return
    
    print("=" * 60)
    print("CruxCam - Command Line Example")
    print("=" * 60)
    print(f"\nInput video: {input_video}")
    print(f"Output video: {output_video}")
    print()
    
    # Get video information
    print("Analyzing video...")
    processor = VideoProcessor()
    try:
        info = processor.get_video_info(input_video)
        print(f"Duration: {info['duration']:.1f}s")
        print(f"Resolution: {info['width']}x{info['height']}")
        print(f"FPS: {info['fps']}")
        print(f"Total frames: {info['total_frames']}")
        print()
    except Exception as e:
        print(f"Error getting video info: {e}")
        return
    
    # Create analyzer with custom threshold
    angle_threshold = 90  # degrees
    analyzer = PoseAnalyzer(angle_threshold=angle_threshold)
    processor = VideoProcessor(pose_analyzer=analyzer)
    
    print(f"Processing video (angle threshold: {angle_threshold}°)...")
    print("This may take a few minutes...\n")
    
    # Progress callback
    def show_progress(current, total):
        percent = (current / total) * 100
        bar_length = 40
        filled = int(bar_length * current / total)
        bar = '█' * filled + '░' * (bar_length - filled)
        print(f"\rProgress: [{bar}] {percent:.1f}% ({current}/{total})", end='', flush=True)
    
    # Process the video
    try:
        result = processor.process_video(
            input_path=input_video,
            output_path=str(output_video),
            progress_callback=show_progress
        )
        
        print("\n")  # New line after progress bar
        print("=" * 60)
        print("RESULTS")
        print("=" * 60)
        print(f"Climbing Efficiency: {result.efficiency:.2f}%")
        print(f"Good Frames: {result.good_frames}")
        print(f"Bad Frames: {result.bad_frames}")
        print(f"Total Analyzed: {result.good_frames + result.bad_frames}")
        print()
        
        # Interpretation
        if result.efficiency >= 70:
            print("✅ Excellent form! You maintained good arm extension.")
        elif result.efficiency >= 50:
            print("⚠️  Room for improvement. Focus on extending your arms more.")
        else:
            print("❌ Consider working on arm extension technique.")
        
        print()
        print(f"Processed video saved to: {output_video}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n\nError processing video: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
