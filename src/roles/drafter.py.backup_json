"""
Agent-OS v3 Drafter Role

Following million-step methodology:
- Generates proposals only (never executes)
- Must include confidence scores
- HALTs on any uncertainty
- All outputs are structured JSON
"""

import os
import sys
import json
import subprocess
import tempfile
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from checkpoints import CheckpointManager
from uncertainty import UncertaintyDetector, Severity, create_halt_result
from notifications import notify_halt, notify_progress
import time

# Cost tracking
try:
    from cost_tracker import track_claude_draft
except ImportError:
    track_claude_draft = None


class Drafter:
    """
    Drafter role: Generates proposals for tasks.
    
    ALLOWED:
    - Read task specifications
    - Read project context and codebase
    - Generate code, documentation, or architecture designs
    - Propose file creations and modifications
    - Self-assess confidence level
    - Flag uncertainties explicitly
    
    NOT ALLOWED:
    - Write directly to filesystem (except /tmp/drafts)
    - Execute shell commands
    - Make git operations
    - Call external APIs with side effects
    - Approve own work
    - Proceed if uncertain
    """
    
    # Path to system prompt
    SYSTEM_PROMPT_PATH = Path('/opt/agent-os-v3/prompts/drafter_system.md')
    SYSTEM_CONTEXT_PATH = Path('/opt/agent-os-v3/prompts/system_context.md')
    
    def __init__(
        self,
        agent_id: str,
        checkpoint_manager: CheckpointManager,
        model: str = "claude-sonnet-4-20250514",
        confidence_threshold: float = 0.70
    ):
        self.agent_id = agent_id
        self.checkpoint_manager = checkpoint_manager
        self.model = model
        self.confidence_threshold = confidence_threshold
        self.uncertainty_detector = UncertaintyDetector(confidence_threshold)
    
    def generate_draft(
        self,
        task: Dict[str, Any],
        project_context: Dict[str, Any],
        relevant_files: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Generate a draft proposal for the task.
        
        Args:
            task: Task specification dict with id, title, description, task_type
            project_context: Project info with name, repo_url, work_dir
            relevant_files: Optional dict of path -> content for context
        
        Returns:
            Result dict with success status, draft, and checkpoint_id
        """
        
        # Create checkpoint BEFORE any work
        checkpoint_id = self.checkpoint_manager.create_checkpoint(
            project_id=str(task.get('project_id', '')),
            task_id=str(task.get('id', '')),
            phase='drafting',
            step_name='generate_draft',
            state_snapshot={
                'task': task,
                'project_context': project_context,
                'files_provided': list(relevant_files.keys()) if relevant_files else []
            },
            inputs={
                'task_id': str(task.get('id', '')),
                'task_title': task.get('title', ''),
                'task_type': task.get('task_type', 'implementation')
            },
            drafter_agent_id=self.agent_id
        )
        
        try:
            # Check required inputs
            missing = self.uncertainty_detector.check_missing_input(
                required=['id', 'title'],
                provided=task
            )
            if missing:
                return self._handle_halt(checkpoint_id, task, missing[0])
            
            # Build prompt
            prompt = self._build_prompt(task, project_context, relevant_files)
            
            # Call LLM
            # Store context for cost tracking
            self._current_project_id = str(task.get('project_id', '')) or None
            self._current_task_id = str(task.get('id', '')) or None
            
            raw_response = self._call_claude(prompt)
            
            # Parse response
            try:
                draft = self._parse_response(raw_response)
            except ValueError as e:
                self.checkpoint_manager.fail_checkpoint(
                    checkpoint_id,
                    {'reason': 'parse_error', 'error': str(e)}
                )
                return {
                    'success': False,
                    'error': f"Failed to parse response: {e}",
                    'checkpoint_id': checkpoint_id
                }
            
            # Check for uncertainty signals in the draft
            if 'reasoning' in draft:
                self.uncertainty_detector.check_uncertainty_language(
                    draft['reasoning'], 
                    source='drafter'
                )
            
            if 'confidence_score' in draft:
                self.uncertainty_detector.check_confidence_score(
                    draft['confidence_score'],
                    source='drafter'
                )
            else:
                # Missing confidence score is itself an uncertainty
                self.uncertainty_detector.signals.append(
                    self.uncertainty_detector.check_confidence_score(0.0, 'drafter')
                )
            
            # Check for explicit uncertainty flags from the drafter
            if draft.get('uncertainty_flags'):
                for flag in draft['uncertainty_flags']:
                    from uncertainty import UncertaintySignal, Category
                    signal = UncertaintySignal(
                        signal_type='drafter_flagged',
                        category=Category.CONFIDENCE,
                        severity=Severity.HALT,
                        description=flag,
                        source='drafter'
                    )
                    self.uncertainty_detector.signals.append(signal)
            
            # If any HALT signals, fail the checkpoint and return
            if self.uncertainty_detector.has_halt_signals():
                halt_signals = self.uncertainty_detector.get_halt_signals()
                self.uncertainty_detector.persist_signals(
                    task_id=str(task.get('id', '')),
                    checkpoint_id=checkpoint_id
                )
                
                self.checkpoint_manager.fail_checkpoint(
                    checkpoint_id,
                    {
                        'reason': 'uncertainty_detected',
                        'signals': [s.to_dict() for s in halt_signals]
                    }
                )
                
                # Notify about HALT
                notify_halt(
                    project_name=project_context.get('name', 'Unknown'),
                    task_title=task.get('title', 'Unknown'),
                    checkpoint_id=checkpoint_id,
                    signal_description=halt_signals[0].description
                )
                
                return {
                    'success': False,
                    'halted': True,
                    'checkpoint_id': checkpoint_id,
                    'uncertainty_signals': [s.to_dict() for s in halt_signals],
                    'message': f"HALT: {halt_signals[0].description}"
                }
            
            # Success! Complete the checkpoint
            self.checkpoint_manager.complete_checkpoint(
                checkpoint_id,
                outputs={
                    'draft': draft,
                    'confidence_score': draft.get('confidence_score'),
                    'files_count': (
                        len(draft.get('files_to_create', [])) + 
                        len(draft.get('files_to_modify', []))
                    )
                },
                rollback_data={'action': 'delete_draft'}
            )
            
            return {
                'success': True,
                'draft': draft,
                'checkpoint_id': checkpoint_id,
                'agent_id': self.agent_id,
                'confidence_score': draft.get('confidence_score', 0)
            }
            
        except Exception as e:
            self.checkpoint_manager.fail_checkpoint(
                checkpoint_id,
                {'reason': 'exception', 'error': str(e)}
            )
            raise
    
    def _handle_halt(
        self, 
        checkpoint_id: int, 
        task: Dict[str, Any],
        signal
    ) -> Dict[str, Any]:
        """Handle a HALT condition."""
        self.checkpoint_manager.fail_checkpoint(
            checkpoint_id,
            {'reason': 'halt', 'signal': signal.to_dict()}
        )
        return create_halt_result(signal, checkpoint_id)
    
    def _build_prompt(
        self,
        task: Dict[str, Any],
        project_context: Dict[str, Any],
        relevant_files: Optional[Dict[str, str]]
    ) -> str:
        """Build the complete prompt for the LLM."""
        
        # Load system prompt
        system_prompt = ""
        if self.SYSTEM_PROMPT_PATH.exists():
            system_prompt = self.SYSTEM_PROMPT_PATH.read_text()
        
        # Load system context (database schema, file structure, conventions)
        system_context = ""
        if self.SYSTEM_CONTEXT_PATH.exists():
            system_context = "\n\n" + self.SYSTEM_CONTEXT_PATH.read_text()
            system_prompt += system_context
        
        # Build user prompt
        user_prompt = f"""## Task

Title: {task.get('title', 'Unknown')}
Type: {task.get('task_type', 'implementation')}
Description: {task.get('description', 'No description provided')}

## Project Context

Project: {project_context.get('name', 'Unknown')}
Repository: {project_context.get('repo_url', 'Unknown')}
Working Directory: {project_context.get('work_dir', 'Unknown')}

"""
        
        if relevant_files:
            user_prompt += "## Relevant Files\n\n"
            for path, content in relevant_files.items():
                # Truncate very long files
                if len(content) > 5000:
                    content = content[:5000] + "\n... (truncated)"
                user_prompt += f"### {path}\n```\n{content}\n```\n\n"
        
        user_prompt += """## Your Task

Generate a proposal for implementing this task. Your response MUST be valid JSON matching the schema in your system prompt.

Remember:
- Include confidence_score (0.0-1.0)
- List any uncertainties in uncertainty_flags
- If confidence < 0.85, explain why

## Your Response (JSON only):
"""
        
        return f"{system_prompt}\n\n---\n\n{user_prompt}"
    
    def _call_claude(self, prompt: str) -> str:
        """
        Call Claude CLI with the prompt.
        
        Uses claude CLI tool if available, falls back to API.
        """
        
        # Write prompt to temp file
        with tempfile.NamedTemporaryFile(
            mode='w', 
            suffix='.txt', 
            delete=False
        ) as f:
            f.write(prompt)
            prompt_file = f.name
        
        try:
            # Try claude CLI first
            result = subprocess.run(
                ['claude', '-p', '--output-format', 'json'], input=prompt,
                capture_output=True,
                text=True,
                timeout=600
            )
            
            if result.returncode == 0:  # CLI succeeded
                # CLI returns JSON wrapper, extract the actual response
                try:
                    cli_output = json.loads(result.stdout)
                    if cli_output.get('is_error'):
                        # CLI reported an error, fall back to API
                        pass
                    else:
                        # Return the actual text response
                        return cli_output.get('result', result.stdout)
                except json.JSONDecodeError:
                    return result.stdout
            
            # If CLI fails, try with API via curl
            # (This is a fallback - in production would use proper API client)
            return self._call_claude_api(prompt)
            
        finally:
            os.unlink(prompt_file)
    
    def _call_claude_api(self, prompt: str) -> str:
        """Fallback to API if CLI unavailable. Tracks costs."""
        
        api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        if not api_key:
            raise RuntimeError("No ANTHROPIC_API_KEY and claude CLI failed")
        
        import urllib.request
        import urllib.parse
        
        data = {
            "model": self.model,
            "max_tokens": 8000,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(data).encode(),
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01"
            }
        )
        
        start_time = time.time()
        try:
            with urllib.request.urlopen(req, timeout=600) as response:
                result = json.loads(response.read())
                latency_ms = int((time.time() - start_time) * 1000)
                
                # Extract usage data
                usage = result.get('usage', {})
                input_tokens = usage.get('input_tokens', 0)
                output_tokens = usage.get('output_tokens', 0)
                
                # Track cost
                if track_claude_draft:
                    try:
                        track_claude_draft(
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            latency_ms=latency_ms,
                            model=self.model,
                            project_id=getattr(self, '_current_project_id', None),
                            task_id=getattr(self, '_current_task_id', None),
                            success=True
                        )
                    except Exception as e:
                        pass  # Don't fail on tracking errors
                
                return result['content'][0]['text']
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            # Track failed request
            if track_claude_draft:
                try:
                    track_claude_draft(
                        input_tokens=len(prompt) // 4,  # Rough estimate
                        output_tokens=0,
                        latency_ms=latency_ms,
                        model=self.model,
                        success=False,
                        error_message=str(e)[:200]
                    )
                except:
                    pass
            raise
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse the JSON response from Claude."""
        
        # Try to find JSON in the response
        import re
        
        # Look for JSON block
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON object
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                json_str = json_match.group()
            else:
                raise ValueError("No JSON found in response")
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")


def create_drafter(
    agent_id: Optional[str] = None,
    model: str = "claude-sonnet-4-20250514"
) -> Drafter:
    """Factory function to create a Drafter instance."""
    
    if agent_id is None:
        agent_id = f"drafter-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    
    checkpoint_manager = CheckpointManager()
    
    return Drafter(
        agent_id=agent_id,
        checkpoint_manager=checkpoint_manager,
        model=model
    )


if __name__ == '__main__':
    # Test the drafter
    print("Testing Drafter role...")
    
    drafter = create_drafter()
    
    # Simple test task
    test_task = {
        'id': 'test-task-001',
        'project_id': 'test-project-001',
        'title': 'Create a hello world script',
        'description': 'Create a simple Python script that prints Hello World',
        'task_type': 'implementation'
    }
    
    test_context = {
        'name': 'test-project',
        'repo_url': 'https://github.com/test/test',
        'work_dir': '/tmp/test'
    }
    
    print(f"Drafter agent ID: {drafter.agent_id}")
    print(f"Task: {test_task['title']}")
    print("Generating draft...")
    
    # Note: This will fail without Claude CLI, but tests the structure
    try:
        result = drafter.generate_draft(test_task, test_context)
        print(f"Result: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"Expected error (no Claude CLI): {e}")
