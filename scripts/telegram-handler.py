#!/usr/bin/env python3
"""
Agent-OS v3 Telegram Webhook Handler
Receives commands from n8n webhook and executes v3 orchestrator commands.
"""

import os
import sys
import json
import subprocess

os.environ.setdefault("DB_HOST", "172.23.0.2")
os.environ.setdefault("DB_NAME", "agent_os_v3")
os.environ.setdefault("DB_USER", "maestro")
os.environ.setdefault("DB_PASSWORD", "maestro_secret_2024")

def run_command(cmd):
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=60
        )
        return result.stdout + result.stderr
    except Exception as e:
        return str(e)

def handle_command(command):
    """Handle a v3 command."""
    cmd = command.strip().lower()
    
    if cmd in ["/v3status", "status"]:
        return run_command("python3 /opt/agent-os-v3/scripts/v3-orchestrator.py status")
    
    elif cmd in ["/v3run", "run"]:
        return run_command("python3 /opt/agent-os-v3/scripts/v3-orchestrator.py run")
    
    elif cmd in ["/v3resume", "resume"]:
        return run_command("python3 /opt/agent-os-v3/scripts/v3-orchestrator.py resume")
    
    elif cmd in ["/v3reset", "reset"]:
        return run_command("python3 /opt/agent-os-v3/scripts/v3-orchestrator.py reset")
    
    elif cmd in ["/v3help", "help"]:
        return """Agent-OS v3 Commands:

/v3status - Show implementation status
/v3run - Continue implementation
/v3resume - Resume from HALT
/v3reset - Reset to beginning
/v3help - Show this help"""
    
    else:
        return f"Unknown command: {command}"

if __name__ == "__main__":
    # Read command from stdin or args
    if len(sys.argv) > 1:
        cmd = " ".join(sys.argv[1:])
    else:
        cmd = sys.stdin.read().strip()
    
    result = handle_command(cmd)
    print(result)

