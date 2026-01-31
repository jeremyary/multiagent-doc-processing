#!/usr/bin/env python3
# This project was developed with assistance from AI tools.
import argparse
import sys
from datetime import datetime
from pathlib import Path

from config import config
from orchestrator import create_orchestrator
from utils.document_cache import document_cache
from utils.human_review import collect_human_review_cli


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Multiagent PDF Processing Workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                                     # Process PDFs from default directory
  python main.py --input-dir ./documents             # Process PDFs from specified directory
  python main.py --limit 5                           # Process only first 5 documents
  python main.py --thread-id <id>                    # Resume workflow or start with specific ID
  python main.py --cache-stats                       # View cache statistics
  python main.py --clear-cache                       # Clear document cache before processing
  python main.py --no-cache                          # Run without document caching
  python main.py --no-checkpointing                  # Run without state checkpointing

Knowledge Base (RAG):
  python main.py --ingest-knowledge                  # Ingest knowledge_base directory docs into RAG vector store
  python main.py --knowledge-stats                   # View knowledge base statistics
  python main.py --clear-knowledge                   # Clear the knowledge base
  python create_knowledge_base.py                    # Generate sample regulation PDFs in knowledge_base directory

Chat History:
  python main.py --chat-stats                        # View chat session statistics
  python main.py --clear-chat-history                # Clear all chat histories

User Memory:
  python main.py --memory-stats                      # View user memory statistics
  python main.py --memory-stats --user <id>          # View facts for specific user
  python main.py --clear-memory                      # Clear all user memory (facts + conversations)
  python main.py --clear-memory --user <id>          # Clear memory for specific user

Environment Variables (see .env.example):
  OPENAI_API_KEY        Required. Your OpenAI API key
  OPENAI_BASE_URL       Optional. Custom endpoint (default: https://api.openai.com/v1)
  OPENAI_MODEL          Optional. Model name (default: gpt-4o-mini)
  LANGFUSE_SECRET_KEY   Optional. Enables LangFuse tracing
  OCR_ENABLED           Optional. Enable OCR for scanned PDFs (default: true)
  RAG_EMBEDDING_MODEL   Optional. HuggingFace model for RAG embeddings
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
        help="Thread ID for checkpointing (resumes if checkpoint exists)"
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
    
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=None,
        metavar="N",
        help="Limit processing to first N documents (default: all)"
    )
    
    # Knowledge Base (RAG) arguments
    parser.add_argument(
        "--ingest-knowledge",
        action="store_true",
        help="Ingest PDFs from knowledge_base/ into RAG vector store"
    )
    
    parser.add_argument(
        "--knowledge-stats",
        action="store_true",
        help="Show RAG knowledge base statistics and exit"
    )
    
    parser.add_argument(
        "--clear-knowledge",
        action="store_true",
        help="Clear the RAG knowledge base"
    )
    
    parser.add_argument(
        "--knowledge-dir",
        type=str,
        default=None,
        help="Directory containing PDFs to ingest (default: ./knowledge_base)"
    )
    
    # Chat history arguments
    parser.add_argument(
        "--chat-stats",
        action="store_true",
        help="Show chat session statistics and exit"
    )
    
    parser.add_argument(
        "--clear-chat-history",
        action="store_true",
        help="Clear all chat session histories"
    )
    
    # User memory arguments
    parser.add_argument(
        "--memory-stats",
        action="store_true",
        help="Show user memory statistics and exit"
    )
    
    parser.add_argument(
        "--clear-memory",
        action="store_true",
        help="Clear user memory (facts and conversation memory)"
    )
    
    parser.add_argument(
        "--user",
        type=str,
        default=None,
        help="User ID for memory operations (e.g., 'admin', 'borrower')"
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
    
    # Handle knowledge base operations
    if args.knowledge_stats:
        from utils.rag import get_rag_manager
        rag = get_rag_manager()
        stats = rag.get_stats()
        print("RAG Knowledge Base Statistics:")
        print(f"  Total chunks:       {stats.get('total_chunks', 0)}")
        print(f"  Persist directory:  {stats.get('persist_directory', 'N/A')}")
        print(f"  Collection:         {stats.get('collection_name', 'N/A')}")
        print(f"  Embedding model:    {stats.get('embedding_model', 'N/A')}")
        return 0
    
    if args.clear_knowledge:
        from utils.rag import get_rag_manager
        rag = get_rag_manager()
        count = rag.clear()
        print(f"Cleared {count} chunks from RAG knowledge base")
        return 0
    
    if args.ingest_knowledge:
        from utils.rag import get_rag_manager
        rag = get_rag_manager()
        knowledge_dir = Path(args.knowledge_dir) if args.knowledge_dir else None
        
        try:
            result = rag.ingest_directory(knowledge_dir)
            if result["files"] > 0:
                print(f"\nKnowledge base ready for RAG queries.")
                return 0
            else:
                print(f"\n[WARNING] No files were ingested.")
                return 1
        except FileNotFoundError as e:
            print(f"[ERROR] {e}")
            print("\nTo create sample knowledge base PDFs, run:")
            print("  python create_knowledge_base.py")
            return 1
    
    # Handle chat history operations
    if args.chat_stats:
        from agents.chat import get_chat_agent
        agent = get_chat_agent()
        sessions = agent.list_sessions()
        print("Chat History Statistics:")
        print(f"  Total sessions: {len(sessions)}")
        print(f"  Database file:  {agent.db_path}")
        if sessions:
            print(f"  Session IDs:")
            for session in sessions[:10]:  # Show first 10
                print(f"    - {session}")
            if len(sessions) > 10:
                print(f"    ... and {len(sessions) - 10} more")
        return 0
    
    if args.clear_chat_history:
        import sqlite3
        try:
            conn = sqlite3.connect(config.APP_DATA_DB_PATH)
            # Clear chat checkpoints (thread_ids containing 'chat-')
            cursor = conn.execute(
                "DELETE FROM checkpoints WHERE thread_id LIKE '%chat-%'"
            )
            count = cursor.rowcount
            conn.commit()
            conn.close()
            print(f"Cleared {count} chat session checkpoints from database")
        except Exception as e:
            print(f"Error clearing chat history: {e}")
        return 0
    
    # Handle user memory operations
    if args.memory_stats:
        from utils.user_memory import get_facts_store, get_conversation_memory
        
        facts_store = get_facts_store()
        conv_memory = get_conversation_memory()
        
        print("User Memory Statistics:")
        print(f"  App database:          {config.APP_DATA_DB_PATH}")
        print(f"  Vector storage:        {config.CHROMA_DB_PATH}")
        
        if args.user:
            facts = facts_store.get_facts(args.user)
            conv_count = conv_memory.get_user_history_count(args.user)
            print(f"\n  User '{args.user}':")
            print(f"    Facts stored:        {len(facts)}")
            print(f"    Conversations:       {conv_count}")
            if facts:
                print(f"    Known facts:")
                for fact_type, details in facts.items():
                    print(f"      - {fact_type}: {details['value']}")
        else:
            stats = facts_store.get_stats()
            print(f"  Users with facts:      {stats['users']}")
            print(f"  Total facts stored:    {stats['facts']}")
            print("\n  Use --memory-stats --user <id> to see a specific user's facts")
        return 0
    
    if args.clear_memory:
        from utils.user_memory import get_facts_store, get_conversation_memory
        
        facts_store = get_facts_store()
        conv_memory = get_conversation_memory()
        
        if args.user:
            # Clear for specific user
            facts_cleared = facts_store.clear_user(args.user)
            conv_cleared = conv_memory.clear_user(args.user)
            print(f"Cleared memory for user '{args.user}':")
            print(f"  Facts cleared:         {facts_cleared}")
            print(f"  Conversations cleared: {conv_cleared}")
        else:
            # Clear all
            facts_cleared = facts_store.clear_all()
            conv_cleared = conv_memory.clear_all()
            print(f"Cleared all user memory:")
            print(f"  Facts cleared:         {facts_cleared}")
            print(f"  Conversations cleared: {conv_cleared}")
        return 0
    
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
    
    # Generate thread_id if not provided
    thread_id = args.thread_id or f"doc-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    # Create and run orchestrator
    try:
        orchestrator = create_orchestrator(
            checkpointing=not args.no_checkpointing
        )
        
        # Execute workflow with human-in-the-loop handler
        final_state, thread_id = orchestrator.run(
            input_directory=str(input_dir),
            thread_id=thread_id,
            session_id=args.session_id,
            use_cache=not args.no_cache,
            doc_limit=args.limit,
            interrupt_handler=collect_human_review_cli
        )
        
        # Return code based on success
        if final_state.get("report_generated"):
            print("\nWorkflow completed successfully!")
            return 0
        elif "__interrupt__" in final_state:
            print(f"\n[INFO] Workflow paused. To resume:")
            print(f"  python main.py --thread-id {thread_id}")
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
