"""AI-powered task suggestion generator using Groq."""
import os
import json
import requests
from typing import Optional, List, Dict, Any

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', 'your-groq-api-key')
GROQ_MODEL = "llama-3.3-70b-versatile"

def generate_ai_suggestions(
    system_state: Dict[str, Any],
    focus_notes: Optional[str] = None,
    max_suggestions: int = 5
) -> List[Dict[str, Any]]:
    """
    Generate AI-powered task suggestions based on current system state.
    
    Args:
        system_state: Dict with keys like 'milestones', 'recent_tasks', 'failed_tasks', 'halted_tasks'
        focus_notes: Optional user-provided focus areas or notes
        max_suggestions: Max number of suggestions to generate
    
    Returns:
        List of suggestion dicts with title, description, priority, milestone_id
    """
    
    # Build context for the AI
    context_parts = []
    
    # Milestone overview
    if system_state.get('milestones'):
        context_parts.append("## Current Milestones")
        for m in system_state['milestones']:
            total = m.get('total_tasks', 0)
            complete = m.get('completed_tasks', 0)
            pct = (complete / total * 100) if total > 0 else 0
            context_parts.append(f"- Phase {m.get('phase_number', '?')}: {m.get('name', 'Unknown')} ({complete}/{total} tasks, {pct:.0f}%)")
            if m.get('description'):
                context_parts.append(f"  Description: {m['description'][:100]}")
    
    # Recent completed tasks
    if system_state.get('recent_complete'):
        context_parts.append("\n## Recently Completed")
        for t in system_state['recent_complete'][:5]:
            context_parts.append(f"- {t.get('title', 'Unknown')}")
    
    # Failed tasks
    if system_state.get('failed_tasks'):
        context_parts.append("\n## Failed Tasks (need retry or redesign)")
        for t in system_state['failed_tasks'][:5]:
            context_parts.append(f"- {t.get('title', 'Unknown')}: {(t.get('last_error') or 'No error details')[:80]}")
    
    # Halted tasks
    if system_state.get('halted_tasks'):
        context_parts.append("\n## Halted Tasks (uncertainty detected)")
        for t in system_state['halted_tasks'][:5]:
            context_parts.append(f"- {t.get('title', 'Unknown')}")
    
    # Pending tasks
    if system_state.get('pending_tasks'):
        context_parts.append("\n## Pending Tasks")
        for t in system_state['pending_tasks'][:5]:
            context_parts.append(f"- {t.get('title', 'Unknown')}")
    
    context = "\n".join(context_parts)
    
    # Build the prompt
    focus_instruction = ""
    if focus_notes:
        focus_instruction = f"""
## User Focus Request
The user wants suggestions focused on: {focus_notes}

Prioritize suggestions that align with this focus.
"""
    
    prompt = f"""You are a technical project manager for Agent-OS v3, an autonomous development system.
Based on the current state, suggest {max_suggestions} actionable tasks.

{context}
{focus_instruction}
## Requirements
- Each task should be specific and achievable in 1-2 hours
- Include clear success criteria in the description
- Prioritize: 1) Fixing failures, 2) Completing current phases, 3) New features
- Tasks should have detailed descriptions that tell the drafter exactly what to do

## Output Format
Return ONLY valid JSON array with objects containing:
- title: Short task title (max 60 chars)
- description: Detailed description with specific requirements (2-4 sentences)
- priority: 1-10 (10 = highest)
- phase: Which phase this belongs to (1-4, or 0 for general)
- task_type: "implementation", "bugfix", "documentation", or "architecture"

Example:
[
  {{"title": "Fix webhook timeout handling", "description": "Add 30s timeout to webhook endpoints in scripts/webhook_trigger.py. Catch timeout exceptions and return 504 status. Log timeout events.", "priority": 8, "phase": 3, "task_type": "bugfix"}}
]

Your response (JSON only, no markdown):"""

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 2000
            },
            timeout=30
        )
        
        if response.status_code != 200:
            return []
        
        result = response.json()
        content = result.get('choices', [{}])[0].get('message', {}).get('content', '[]')
        
        # Parse JSON - handle potential markdown wrapping
        content = content.strip()
        if content.startswith('```'):
            content = content.split('```')[1]
            if content.startswith('json'):
                content = content[4:]
        
        suggestions = json.loads(content)
        
        # Validate and normalize
        validated = []
        for s in suggestions[:max_suggestions]:
            if isinstance(s, dict) and 'title' in s and 'description' in s:
                validated.append({
                    'title': str(s.get('title', ''))[:60],
                    'description': str(s.get('description', '')),
                    'priority': min(10, max(1, int(s.get('priority', 5)))),
                    'phase': int(s.get('phase', 0)),
                    'task_type': s.get('task_type', 'implementation'),
                    'ai_generated': True
                })
        
        return validated
        
    except Exception as e:
        print(f"AI suggestion error: {e}")
        return []


if __name__ == "__main__":
    # Test
    test_state = {
        'milestones': [
            {'name': 'Core Infrastructure', 'phase_number': 1, 'total_tasks': 10, 'completed_tasks': 8},
            {'name': 'Role-Based Agents', 'phase_number': 2, 'total_tasks': 8, 'completed_tasks': 5},
        ],
        'failed_tasks': [
            {'title': 'Add webhook endpoint', 'last_error': 'Timezone uncertainty'}
        ]
    }
    
    results = generate_ai_suggestions(test_state, focus_notes="improve error handling")
    print(json.dumps(results, indent=2))
