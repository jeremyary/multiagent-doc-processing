#!/usr/bin/env python3
# This project was developed with assistance from AI tools.
import argparse
import sys
from pathlib import Path

from config import config
from orchestrator import create_orchestrator
from utils.document_cache import document_cache


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Multiagent PDF Processing Workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                           # Process PDFs from default input_pdfs directory
  python main.py --input-dir ./documents   # Process PDFs from specified directory
  python main.py --no-checkpointing        # Run without state checkpointing
  python main.py --cache-stats             # View cache statistics
  python main.py --clear-cache             # Clear document cache before processing
  python main.py --no-cache                # Run without document caching

Environment Variables (see .env.example):
  OPENAI_API_KEY        Required. Your OpenAI API key
  OPENAI_BASE_URL       Optional. Custom endpoint (default: https://api.openai.com/v1)
  OPENAI_MODEL          Optional. Model name (default: gpt-4o-mini)
  LANGFUSE_SECRET_KEY   Optional. Enables LangFuse tracing
  OCR_ENABLED           Optional. Enable OCR for scanned PDFs (default: true)
        """
    )
    
    parser.add_argument(
        "--input-dir", "-i",
        type=str,
        default=None,
        help="Directory containing PDF files to process (default: ./input_pdfs)"
    )
    
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default=None,
        help="Directory for output reports (default: ./output_reports)"
    )
    
    parser.add_argument(
        "--no-checkpointing",
        action="store_true",
        help="Disable workflow state checkpointing"
    )
    
    parser.add_argument(
        "--thread-id",
        type=str,
        default=None,
        help="Thread ID for checkpointing (enables resumable workflows)"
    )
    
    parser.add_argument(
        "--session-id",
        type=str,
        default=None,
        help="Session ID for LangFuse tracking"
    )
    
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear the document cache before processing"
    )
    
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable document caching for this run"
    )
    
    parser.add_argument(
        "--cache-stats",
        action="store_true",
        help="Show cache statistics and exit"
    )
    
    return parser.parse_args()


def validate_environment() -> bool:
    """Validate the environment and configuration."""
    try:
        config.validate()
        return True
    except ValueError as e:
        print(f"[ERROR] Configuration Error: {e}")
        print("\nPlease ensure you have:")
        print("  1. Created a .env file with your OPENAI_API_KEY")
        print("  2. Or set the OPENAI_API_KEY environment variable")
        return False


def main() -> int:
    """Main entry point."""
    args = parse_args()
    
    # Handle cache-only operations
    if args.cache_stats:
        stats = document_cache.get_stats()
        print("Document Cache Statistics:")
        print(f"  Total documents cached: {stats['total_documents']}")
        print(f"  With extraction data:   {stats['with_extraction']}")
        print(f"  With classification:    {stats['with_classification']}")
        print(f"  Cache file: {document_cache.cache_path.absolute()}")
        return 0
    
    if args.clear_cache:
        count = document_cache.clear()
        print(f"Cleared {count} entries from document cache")
    
    # Validate environment
    if not validate_environment():
        return 1
    
    # Configure directories
    if args.input_dir:
        input_dir = Path(args.input_dir)
    else:
        input_dir = config.INPUT_PDF_DIR
    
    if args.output_dir:
        config.OUTPUT_REPORT_DIR = Path(args.output_dir)
    
    # Ensure input directory exists
    if not input_dir.exists():
        print(f"[ERROR] Input directory does not exist: {input_dir}")
        print(f"   Creating directory... Add PDF files to: {input_dir}")
        input_dir.mkdir(parents=True, exist_ok=True)
        return 1
    
    # Check for PDF files
    pdf_files = list(input_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"[WARNING] No PDF files found in: {input_dir}")
        print("   Please add PDF files to the input directory and run again.")
        return 1
    
    print(f"Input Directory: {input_dir}")
    print(f"PDF Files Found: {len(pdf_files)}")
    
    # Display cache info
    if not args.no_cache:
        stats = document_cache.get_stats()
        if stats['total_documents'] > 0:
            print(f"Document Cache: {stats['total_documents']} documents cached (use --clear-cache to reset)")
    else:
        print("Document Cache: Disabled for this run")
    
    # Create and run orchestrator
    try:
        orchestrator = create_orchestrator(
            checkpointing=not args.no_checkpointing
        )
        
        # Execute workflow
        final_state = orchestrator.run(
            input_directory=str(input_dir),
            thread_id=args.thread_id,
            session_id=args.session_id,
            use_cache=not args.no_cache
        )
        
        # Return code based on success
        if final_state.get("report_generated"):
            print("\nWorkflow completed successfully!")
            return 0
        else:
            print("\n[WARNING] Workflow completed with issues.")
            return 1
            
    except KeyboardInterrupt:
        print("\n\n[WARNING] Workflow interrupted by user")
        return 130
    except Exception as e:
        print(f"\n[ERROR] Workflow failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
