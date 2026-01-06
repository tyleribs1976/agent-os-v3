#!/usr/bin/env python3
"""
Agent-OS v3 Task Auto-Improver

Automatically analyzes halted/failed tasks and improves their descriptions
by embedding actual file contents and resolving uncertainty signals.
"""

import os
import sys
import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add path for imports
sys.path.insert(0, '/opt/agent-os-v3/src')

from db import query_all, query_one, update

# Anthropic API for analysis
import urllib.request


ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')


def call_claude(prompt: str, max_tokens: int = 4000) -> str:
    """Call Claude API for analysis."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    
    data = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }
    
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(data).encode(),
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01"
        }
    )
    
    with urllib.request.urlopen(req, timeout=120) as response:
        result = json.loads(response.read())
        return result['content'][0]['text']


def get_failed_tasks() -> List[Dict[str, Any]]:
    """Get all halted/failed tasks with their checkpoint errors."""
    tasks = query_all("""
        SELECT DISTINCT ON (t.id)
            t.id, t.title, t.description, t.status,
            c.error_details
        FROM tasks t
        LEFT JOIN checkpoints c ON c.task_id = t.id AND c.status = 'failed'
        WHERE t.status IN ('halted', 'failed')
        ORDER BY t.id, c.created_at DESC
    """)
    return tasks or []


def extract_referenced_files(description: str) -> List[str]:
    """Extract file paths referenced in task description."""
    patterns = [
        r'/opt/[^\s\'"`,\)\]]+\.py',
        r'/opt/[^\s\'"`,\)\]]+\.json',
        r'/opt/[^\s\'"`,\)\]]+\.yaml',
        r'/opt/[^\s\'"`,\)\]]+\.md',
        r'src/[^\s\'"`,\)\]]+\.py',
    ]
    
    files = []
    for pattern in patterns:
        matches = re.findall(pattern, description)
        files.extend(matches)
    
    return list(set(files))


def read_file_safely(path: str, max_lines: int = 100) -> Optional[str]:
    """Read file contents safely, truncating if too long."""
    if not path.startswith('/'):
        path = f'/opt/agent-os-v3/{path}'
    
    try:
        with open(path, 'r') as f:
            lines = f.readlines()
            if len(lines) > max_lines:
                content = ''.join(lines[:max_lines])
                content += f"\n... (truncated, {len(lines) - max_lines} more lines)"
            else:
                content = ''.join(lines)
            return content
    except FileNotFoundError:
        return None
    except Exception as e:
        return f"Error reading file: {e}"


def get_db_schema_info() -> str:
    """Get relevant database schema information."""
    tables_info = []
    
    for table in ['tasks', 'checkpoints', 'projects']:
        columns = query_all(f"""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = '{table}'
            ORDER BY ordinal_position
        """)
        if columns:
            cols = ', '.join([f"{c['column_name']}:{c['data_type']}" for c in columns])
            tables_info.append(f"{table}: {cols}")
    
    return '\n'.join(tables_info)


def analyze_and_improve_task(task: Dict[str, Any]) -> Optional[str]:
    """Analyze task failure and generate improved description."""
    
    task_id = task['id']
    title = task['title']
    description = task['description'] or ''
    error_details = task.get('error_details', {})
    
    if isinstance(error_details, str):
        try:
            error_details = json.loads(error_details)
        except:
            error_details = {'raw_error': error_details}
    
    referenced_files = extract_referenced_files(description)
    file_contents = {}
    
    for filepath in referenced_files:
        content = read_file_safely(filepath)
        if content:
            file_contents[filepath] = content
    
    db_schema = get_db_schema_info()
    
    prompt = f"""You are improving a task description for an autonomous AI coding system.
The task previously failed or halted. Your job is to rewrite the description to be 
completely self-contained with all needed context embedded directly.

TASK TITLE: {title}

CURRENT DESCRIPTION:
{description}

FAILURE/HALT REASON:
{json.dumps(error_details, indent=2, default=str)}

DATABASE SCHEMA:
{db_schema}

FILE CONTENTS FOUND:
"""
    
    for filepath, content in file_contents.items():
        prompt += f"\n--- {filepath} ---\n{content}\n"
    
    if not file_contents:
        prompt += "(No referenced files found or readable)\n"
    
    prompt += """

INSTRUCTIONS:
1. Analyze why the task failed/halted
2. Write a NEW, IMPROVED description that:
   - Embeds all necessary file contents and schemas directly
   - Removes any "first examine" or "query to find" instructions - include the answers
   - Specifies exact imports, class names, method signatures from the actual code
   - Provides complete, copy-paste ready code snippets where helpful
   - Is specific enough that a coding AI can complete it with 95%+ confidence

3. If the failure was due to git/execution issues (not task clarity), note that and 
   suggest the task can be retried as-is.

4. Output ONLY the new description text, nothing else. No preamble.
   Start directly with the improved task description.
"""
    
    try:
        improved = call_claude(prompt)
        return improved.strip()
    except Exception as e:
        print(f"  Error calling Claude: {e}")
        return None


def fix_git_state():
    """Fix common git state issues."""
    import subprocess
    
    work_dir = '/opt/agent-os/work/agent-os'
    
    try:
        subprocess.run(['git', 'checkout', 'main'], cwd=work_dir, capture_output=True)
        subprocess.run(['git', 'pull', 'origin', 'main'], cwd=work_dir, capture_output=True)
        
        result = subprocess.run(
            ['git', 'branch', '--list', 'aos/*'],
            cwd=work_dir, capture_output=True, text=True
        )
        branches = [b.strip() for b in result.stdout.split('\n') if b.strip()]
        
        for branch in branches[:10]:
            if branch and not branch.startswith('*'):
                subprocess.run(['git', 'branch', '-D', branch], cwd=work_dir, capture_output=True)
        
        print(f"  Cleaned up {len(branches)} old branches")
        return True
    except Exception as e:
        print(f"  Git cleanup error: {e}")
        return False


def update_task_description(task_id: str, new_description: str) -> bool:
    """Update task description in database."""
    try:
        rows = update('tasks', {
            'description': new_description,
            'status': 'queued',
            'updated_at': datetime.utcnow()
        }, {'id': task_id})
        return rows > 0
    except Exception as e:
        print(f"  Database update error: {e}")
        return False


def main():
    print("=" * 60)
    print("Agent-OS v3 Task Auto-Improver")
    print("=" * 60)
    
    print("\n[1] Fixing git state...")
    fix_git_state()
    
    print("\n[2] Finding halted/failed tasks...")
    tasks = get_failed_tasks()
    print(f"  Found {len(tasks)} tasks to improve")
    
    if not tasks:
        print("  No tasks need improvement!")
        return
    
    improved_count = 0
    
    for task in tasks:
        print(f"\n[Processing] {task['title']}")
        print(f"  ID: {task['id']}")
        print(f"  Status: {task['status']}")
        
        error = task.get('error_details', {})
        if isinstance(error, dict):
            reason = error.get('reason', '')
            if reason == 'execution_failed' and 'git' in str(error.get('failed_step', '')).lower():
                print("  -> Git execution issue, resetting to queued for retry")
                update_task_description(task['id'], task['description'])
                improved_count += 1
                continue
        
        print("  -> Analyzing and improving description...")
        improved_desc = analyze_and_improve_task(task)
        
        if improved_desc:
            print("  -> Updating task with improved description")
            if update_task_description(task['id'], improved_desc):
                improved_count += 1
                print("  -> SUCCESS")
            else:
                print("  -> FAILED to update database")
        else:
            print("  -> Could not generate improvement")
    
    print("\n" + "=" * 60)
    print(f"Improved {improved_count}/{len(tasks)} tasks")
    print("=" * 60)


if __name__ == '__main__':
    main()
