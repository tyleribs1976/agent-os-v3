#!/usr/bin/env python3
"""
Agent-OS v3 Command Line Interface

Provides CLI commands for interacting with the Agent-OS v3 system:
- run: Execute the task orchestrator
- status: View current task status
- version: Display version information

Following million-step methodology:
- Explicit argument parsing with validation
- Clear error messages for invalid inputs
- Consistent output formatting
"""

import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from constants import (
    VERSION, BUILD_NUMBER, RELEASE_DATE, APP_NAME, AUTHOR,
    PROJECT_NAME, DESCRIPTION
)


def create_parser() -> argparse.ArgumentParser:
    """
    Create the argument parser with subcommands.
    
    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog='agent-os',
        description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Add version flag to main parser
    parser.add_argument(
        '--version',
        action='version',
        version=f'{APP_NAME} v{VERSION} (build {BUILD_NUMBER}, {RELEASE_DATE})'
    )
    
    # Create subparsers for commands
    subparsers = parser.add_subparsers(
        dest='command',
        help='Available commands',
        required=False
    )
    
    # run command - execute the orchestrator
    run_parser = subparsers.add_parser(
        'run',
        help='Run the task orchestrator'
    )
    run_parser.add_argument(
        '--project-id',
        type=str,
        help='Optional project ID to filter tasks (UUID format)'
    )
    run_parser.add_argument(
        '--task-id',
        type=str,
        help='Optional specific task ID to run (UUID format)'
    )
    run_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate execution without making changes'
    )
    
    # status command - view task status
    status_parser = subparsers.add_parser(
        'status',
        help='View task status'
    )
    status_parser.add_argument(
        '--task-id',
        type=str,
        help='Specific task ID to check (UUID format)'
    )
    status_parser.add_argument(
        '--project-id',
        type=str,
        help='Filter by project ID (UUID format)'
    )
    status_parser.add_argument(
        '--all',
        action='store_true',
        help='Show all tasks including completed'
    )
    status_parser.add_argument(
        '--format',
        choices=['table', 'json', 'simple'],
        default='table',
        help='Output format (default: table)'
    )
    
    # version command - display version info
    version_parser = subparsers.add_parser(
        'version',
        help='Display version information'
    )
    version_parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed version information'
    )
    
    return parser


def cmd_run(args: argparse.Namespace) -> int:
    """
    Execute the run command.
    
    Args:
        args: Parsed command line arguments
    
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        from orchestrator import TaskOrchestrator
        from validators import validate_task_id, validate_project_id, ValidationError
        
        # Validate UUIDs if provided
        if args.project_id:
            try:
                args.project_id = validate_project_id(args.project_id)
            except ValidationError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1
        
        if args.task_id:
            try:
                args.task_id = validate_task_id(args.task_id)
            except ValidationError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1
        
        orchestrator = TaskOrchestrator()
        
        if args.dry_run:
            print("[DRY RUN MODE]")
            # TODO: Implement dry run logic
            print("Dry run not yet implemented")
            return 0
        
        # Get next task
        if args.task_id:
            print(f"Running specific task: {args.task_id}")
            # TODO: Implement specific task execution
            print("Specific task execution not yet implemented")
            return 0
        else:
            print("Getting next queued task...")
            task = orchestrator.get_next_task(project_id=args.project_id)
            
            if not task:
                print("No tasks in queue")
                return 0
            
            print(f"Processing task: {task['id']} - {task['title']}")
            # TODO: Implement full orchestration
            print("Full orchestration not yet implemented")
            return 0
    
    except Exception as e:
        print(f"Error running orchestrator: {e}", file=sys.stderr)
        return 1


def cmd_status(args: argparse.Namespace) -> int:
    """
    Execute the status command.
    
    Args:
        args: Parsed command line arguments
    
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        from db import query_one, query_all
        from validators import validate_task_id, validate_project_id, ValidationError
        import json
        
        # Validate UUIDs if provided
        if args.task_id:
            try:
                args.task_id = validate_task_id(args.task_id)
            except ValidationError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1
        
        if args.project_id:
            try:
                args.project_id = validate_project_id(args.project_id)
            except ValidationError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1
        
        # Build query
        if args.task_id:
            sql = "SELECT * FROM tasks WHERE id = %s"
            params = (args.task_id,)
            task = query_one(sql, params)
            tasks = [task] if task else []
        else:
            sql = "SELECT * FROM tasks"
            params = []
            
            if args.project_id:
                sql += " WHERE project_id = %s"
                params.append(args.project_id)
            
            if not args.all:
                if args.project_id:
                    sql += " AND status NOT IN ('complete', 'failed')"
                else:
                    sql += " WHERE status NOT IN ('complete', 'failed')"
            
            sql += " ORDER BY priority ASC, created_at ASC"
            tasks = query_all(sql, tuple(params) if params else None)
        
        if not tasks:
            print("No tasks found")
            return 0
        
        # Format output
        if args.format == 'json':
            # Convert datetime objects to strings for JSON serialization
            import datetime
            def json_serial(obj):
                if isinstance(obj, datetime.datetime):
                    return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")
            
            print(json.dumps(tasks, indent=2, default=json_serial))
        
        elif args.format == 'simple':
            for task in tasks:
                print(f"{task['id']}: {task['title']} [{task['status']}]")
        
        else:  # table format
            print(f"{'ID':<38} {'Title':<40} {'Status':<12} {'Phase':<20}")
            print("-" * 110)
            for task in tasks:
                task_id = str(task['id'])[:36]
                title = task['title'][:40]
                status = task['status'][:12]
                phase = task['current_phase'][:20]
                print(f"{task_id:<38} {title:<40} {status:<12} {phase:<20}")
        
        return 0
    
    except Exception as e:
        print(f"Error getting status: {e}", file=sys.stderr)
        return 1


def cmd_version(args: argparse.Namespace) -> int:
    """
    Execute the version command.
    
    Args:
        args: Parsed command line arguments
    
    Returns:
        Exit code (0 for success)
    """
    if args.verbose:
        print(f"{PROJECT_NAME}")
        print(f"Version: {VERSION}")
        print(f"Build: {BUILD_NUMBER}")
        print(f"Release Date: {RELEASE_DATE}")
        print(f"Author: {AUTHOR}")
        print()
        print(DESCRIPTION)
    else:
        print(f"{APP_NAME} v{VERSION}")
    
    return 0


def main() -> int:
    """
    Main entry point for CLI.
    
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = create_parser()
    args = parser.parse_args()
    
    # If no command specified, show help
    if not args.command:
        parser.print_help()
        return 0
    
    # Dispatch to command handler
    if args.command == 'run':
        return cmd_run(args)
    elif args.command == 'status':
        return cmd_status(args)
    elif args.command == 'version':
        return cmd_version(args)
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
