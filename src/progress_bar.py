import os
import time
import json
import urllib.request
import urllib.parse
from typing import Optional

# Phase configuration with emojis and display names
PHASE_CONFIG = {
    "initializing": {"emoji": "🔄", "name": "Initializing", "order": 0},
    "drafting": {"emoji": "✏️", "name": "Drafting", "order": 1},
    "drafting_complete": {"emoji": "✏️", "name": "Draft Complete", "order": 1},
    "verification": {"emoji": "🔍", "name": "Verification", "order": 2},
    "verifying": {"emoji": "🔍", "name": "Verifying", "order": 2},
    "verification_complete": {"emoji": "🔍", "name": "Verified", "order": 2},
    "compliance": {"emoji": "📋", "name": "Compliance", "order": 3},
    "compliance_complete": {"emoji": "📋", "name": "Compliance OK", "order": 3},
    "execution": {"emoji": "⚙️", "name": "Execution", "order": 4},
    "executing": {"emoji": "⚙️", "name": "Executing", "order": 4},
    "committing": {"emoji": "💾", "name": "Committing", "order": 5},
    "pushing": {"emoji": "🚀", "name": "Pushing", "order": 6},
    "creating_pr": {"emoji": "🔗", "name": "Creating PR", "order": 7},
    "creating pr": {"emoji": "🔗", "name": "Creating PR", "order": 7},
    "complete": {"emoji": "✅", "name": "Complete", "order": 8},
    "working": {"emoji": "⚙️", "name": "Working", "order": 4},
}

# Pipeline stages for visualization
PIPELINE_STAGES = ["Draft", "Verify", "Execute", "PR"]


class TelegramProgressBar:
    def __init__(self, token: str = None, chat_id: str = None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "8225207052:AAHRPqVqUupJnIbTrhCyr12Ki7-oWWpsHT8")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "5476253866")
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.message_id = None
        self.task_title = None
        self.task_id = None
        self.start_time = None
        self.last_percentage = 0
        self.current_phase = "initializing"

    def _generate_bar(self, pct: int) -> str:
        filled = pct // 5
        empty = 20 - filled
        return "▓" * filled + "░" * empty

    def _generate_pipeline(self, phase: str) -> str:
        """Generate a visual pipeline showing current stage."""
        phase_lower = phase.lower()
        config = PHASE_CONFIG.get(phase_lower, {"order": 0})
        current_order = config.get("order", 0)
        
        # Map order to pipeline stage
        # 0-1: Draft, 2-3: Verify, 4-5: Execute, 6-7: PR
        stage_map = {0: 0, 1: 0, 2: 1, 3: 1, 4: 2, 5: 2, 6: 3, 7: 3, 8: 3}
        current_stage = stage_map.get(current_order, 0)
        
        parts = []
        for i, stage in enumerate(PIPELINE_STAGES):
            if i < current_stage:
                parts.append(f"✅ {stage}")
            elif i == current_stage:
                parts.append(f"▶️ *{stage}*")
            else:
                parts.append(f"⬜ {stage}")
        
        return " → ".join(parts)

    def _get_phase_display(self, phase: str) -> tuple:
        """Get emoji and display name for a phase."""
        phase_lower = phase.lower()
        config = PHASE_CONFIG.get(phase_lower, {"emoji": "📊", "name": phase.title()})
        return config["emoji"], config["name"]

    def _format_time(self, seconds: int) -> str:
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        if h > 0:
            return f"{h}h {m}m {s}s"
        elif m > 0:
            return f"{m}m {s}s"
        return f"{s}s"

    def _estimate_remaining(self, pct: int, elapsed: int) -> str:
        if pct <= 0:
            return "calculating..."
        total = elapsed * 100 // pct
        remaining = max(0, total - elapsed)
        return self._format_time(remaining)

    def _send_message(self, text: str) -> dict:
        try:
            data = urllib.parse.urlencode({
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }).encode()
            req = urllib.request.Request(f"{self.api_url}/sendMessage", data=data, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except Exception as e:
            print(f"Send failed: {e}")
            return {}

    def _edit_message(self, text: str) -> bool:
        try:
            data = urllib.parse.urlencode({
                "chat_id": self.chat_id,
                "message_id": self.message_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }).encode()
            req = urllib.request.Request(f"{self.api_url}/editMessageText", data=data, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read()).get("ok", False)
        except Exception as e:
            print(f"Edit failed: {e}")
            return False

    def start(self, task_title: str, task_id: str, agent: str = "claude") -> Optional[int]:
        self.task_title = task_title
        self.task_id = task_id
        self.start_time = time.time()
        self.last_percentage = 0
        self.current_phase = "initializing"
        
        bar = self._generate_bar(0)
        pipeline = self._generate_pipeline("initializing")
        
        msg = f"""🚀 <b>Task Started</b>

<b>Task:</b> {task_title}
<b>ID:</b> <code>{task_id}</code>
<b>Agent:</b> {agent}

{bar} 0%

{pipeline}

⏱ *Elapsed:* 0s
🔄 *Phase:* Initializing..."""
        
        resp = self._send_message(msg)
        self.message_id = resp.get("result", {}).get("message_id")
        return self.message_id

    def update(self, pct: int, phase: str = "working", details: str = None) -> bool:
        if self.message_id is None:
            return False
        if pct - self.last_percentage < 5 and phase.lower() == self.current_phase.lower():
            return False
        
        self.last_percentage = pct
        self.current_phase = phase
        
        elapsed = int(time.time() - self.start_time)
        bar = self._generate_bar(pct)
        remaining = self._estimate_remaining(pct, elapsed)
        elapsed_fmt = self._format_time(elapsed)
        pipeline = self._generate_pipeline(phase)
        phase_emoji, phase_name = self._get_phase_display(phase)
        
        msg = f"""🔄 *Task In Progress*

*Task:* {self.task_title}
*ID:* `{self.task_id}`

{bar} {pct}%

{pipeline}

⏱ *Elapsed:* {elapsed_fmt}
⏳ *Remaining:* ~{remaining}
{phase_emoji} *Phase:* {phase_name}"""
        
        if details:
            msg += f"\n\n📋 {details}"
        
        return self._edit_message(msg)

    def complete(self, status: str = "complete", summary: str = None) -> bool:
        if self.message_id is None:
            return False
        
        elapsed = int(time.time() - self.start_time)
        elapsed_fmt = self._format_time(elapsed)
        
        icons = {"complete": "✅", "failed": "❌", "halted": "🛑", "cancelled": "⛔"}
        texts = {"complete": "Completed", "failed": "Failed", "halted": "Halted", "cancelled": "Cancelled"}
        
        icon = icons.get(status, "✅")
        status_text = texts.get(status, "Completed")
        
        if status == "complete":
            bar = "▓" * 20
            pct = 100
            pipeline = "✅ Draft → ✅ Verify → ✅ Execute → ✅ PR"
        else:
            bar = "▓" * (self.last_percentage // 5) + "░" * (20 - self.last_percentage // 5)
            pct = self.last_percentage
            pipeline = self._generate_pipeline(self.current_phase)
        
        msg = f"""{icon} *Task {status_text}*

*Task:* {self.task_title}
*ID:* `{self.task_id}`

{bar} {pct}%

{pipeline}

⏱ *Total Time:* {elapsed_fmt}"""
        
        if summary:
            msg += f"\n\n📋 *Summary:* {summary}"
        
        return self._edit_message(msg)
