"""
Agent-OS v3 Notification Module

Handles all external notifications:
- Telegram for interactive alerts
- Pushover for emergency alerts
"""

import os
import json
import urllib.request
import urllib.parse
from typing import Optional, Dict, Any


class TelegramNotifier:
    """Send notifications via Telegram bot."""
    
    def __init__(
        self,
        token: str = None,
        chat_id: str = None
    ):
        self.token = token or os.environ.get(
            'TELEGRAM_BOT_TOKEN',
            '8225207052:AAHRPqVqUupJnIbTrhCyr12Ki7-oWWpsHT8'
        )
        self.chat_id = chat_id or os.environ.get(
            'TELEGRAM_CHAT_ID',
            '5476253866'
        )
        self.api_url = f"https://api.telegram.org/bot{self.token}"
    
    def send_message(
        self,
        text: str,
        parse_mode: str = "HTML",
        disable_preview: bool = True
    ) -> bool:
        """
        Send a message via Telegram.
        
        Args:
            text: Message text (supports Markdown)
            parse_mode: "Markdown" or "HTML"
            disable_preview: Don't show link previews
        
        Returns:
            True if sent successfully
        """
        try:
            data = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': parse_mode,
                'disable_web_page_preview': disable_preview
            }
            
            req = urllib.request.Request(
                f"{self.api_url}/sendMessage",
                data=urllib.parse.urlencode(data).encode(),
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read())
                return result.get('ok', False)
                
        except Exception as e:
            print(f"Telegram send failed: {e}")
            return False


class PushoverNotifier:
    """Send notifications via Pushover for urgent alerts."""
    
    def __init__(
        self,
        user_key: str = None,
        api_token: str = None
    ):
        self.user_key = user_key or os.environ.get(
            'PUSHOVER_USER_KEY',
            'usotnzpu144ctz3avvxxmyi4pf8qjc'
        )
        self.api_token = api_token or os.environ.get(
            'PUSHOVER_API_TOKEN',
            'aky2m5f3r54nyecb8qxtewy1w98bvk'
        )
        self.api_url = "https://api.pushover.net/1/messages.json"
    
    def send_message(
        self,
        title: str,
        message: str,
        priority: int = 0,
        sound: str = "pushover"
    ) -> bool:
        """
        Send a Pushover notification.
        
        Args:
            title: Message title
            message: Message body
            priority: -2 (lowest) to 2 (emergency)
            sound: Alert sound name
        
        Returns:
            True if sent successfully
        """
        try:
            data = {
                'token': self.api_token,
                'user': self.user_key,
                'title': title,
                'message': message,
                'priority': priority,
                'sound': sound
            }
            
            # For emergency priority, add retry/expire
            if priority == 2:
                data['retry'] = 60
                data['expire'] = 3600
            
            req = urllib.request.Request(
                self.api_url,
                data=urllib.parse.urlencode(data).encode(),
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read())
                return result.get('status', 0) == 1
                
        except Exception as e:
            print(f"Pushover send failed: {e}")
            return False


class NotificationManager:
    """
    Unified notification manager for Agent-OS v3.
    
    Routes notifications based on severity and type.
    """
    
    def __init__(self):
        self.telegram = TelegramNotifier()
        self.pushover = PushoverNotifier()
    
    def notify_halt(
        self,
        project_name: str,
        task_title: str,
        checkpoint_id: int,
        signal_description: str
    ) -> None:
        """
        Send notification for a HALT event.
        
        Goes to both Telegram and Pushover (high priority).
        """
        telegram_msg = f"""🛑 <b>HALT: Agent-OS v3</b>

📁 Project: {project_name}
📋 Task: {task_title}
🔖 Checkpoint: #{checkpoint_id}

⚠️ {signal_description}

Action Required: Review and resolve"""
        
        self.telegram.send_message(telegram_msg)
        self.pushover.send_message(
            title="Agent-OS HALT",
            message=f"{task_title}: {signal_description}",
            priority=1,
            sound="siren"
        )
    
    def notify_success(
        self,
        project_name: str,
        task_title: str,
        pr_url: Optional[str] = None,
        duration_seconds: Optional[int] = None
    ) -> None:
        """Send notification for successful task completion."""
        duration_str = f"⏱️ {duration_seconds}s" if duration_seconds else ""
        pr_str = f"\n🔗 {pr_url}" if pr_url else ""
        
        msg = f"""✅ <b>Task Complete</b>

📁 {project_name}
📋 {task_title}
{duration_str}{pr_str}"""
        
        self.telegram.send_message(msg)
    
    def notify_error(
        self,
        project_name: str,
        task_title: str,
        error: str,
        checkpoint_id: Optional[int] = None
    ) -> None:
        """Send notification for an error."""
        checkpoint_str = f"\n🔖 Checkpoint: #{checkpoint_id}" if checkpoint_id else ""
        
        msg = f"""❌ <b>Error: Agent-OS v3</b>

📁 {project_name}
📋 {task_title}{checkpoint_str}

<pre>{error[:500]}</pre>"""
        
        self.telegram.send_message(msg)
        self.pushover.send_message(
            title="Agent-OS Error",
            message=f"{task_title}: {error[:200]}",
            priority=0
        )
    
    def notify_progress(
        self,
        message: str
    ) -> None:
        """Send a progress update (Telegram only)."""
        self.telegram.send_message(f"🔄 *Agent-OS v3*\n\n{message}")
    
    def notify_escalation(
        self,
        project_name: str,
        task_title: str,
        reason: str,
        risk_flags: list
    ) -> None:
        """Send notification for compliance escalation."""
        flags_str = "\n".join([f"  • {f}" for f in risk_flags])
        
        msg = f"""⚠️ *Escalation Required*

📁 {project_name}
📋 {task_title}

Reason: {reason}

Risk Flags:
{flags_str}

Human review required before proceeding."""
        
        self.telegram.send_message(msg)
        self.pushover.send_message(
            title="Agent-OS Escalation",
            message=f"{task_title}: {reason}",
            priority=1,
            sound="intermission"
        )


# Global instance
_notification_manager: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    """Get the global notification manager."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager


def notify_halt(
    project_name: str,
    task_title: str,
    checkpoint_id: int,
    signal_description: str
) -> None:
    """Convenience function for halt notification."""
    get_notification_manager().notify_halt(
        project_name, task_title, checkpoint_id, signal_description
    )


def notify_success(
    project_name: str,
    task_title: str,
    pr_url: Optional[str] = None,
    duration_seconds: Optional[int] = None
) -> None:
    """Convenience function for success notification."""
    get_notification_manager().notify_success(
        project_name, task_title, pr_url, duration_seconds
    )


def notify_error(
    project_name: str,
    task_title: str,
    error: str,
    checkpoint_id: Optional[int] = None
) -> None:
    """Convenience function for error notification."""
    get_notification_manager().notify_error(
        project_name, task_title, error, checkpoint_id
    )


if __name__ == '__main__':
    # Test
    print("Testing NotificationManager...")
    manager = NotificationManager()
    
    # Send test message
    result = manager.telegram.send_message(
        "🧪 *Test from Agent-OS v3*\n\nNotification module initialized successfully."
    )
    print(f"Telegram test: {'✓' if result else '✗'}")

def notify_progress(message: str) -> bool:
    """Shortcut for progress notification."""
    return NotificationManager().notify_progress(message)


def notify_escalation(project_name=None, task_title=None, reason=None, risk_flags=None, message=None, level="high"):
    """Shortcut for escalation notification - supports both signatures."""
    if message:
        return NotificationManager().notify_halt(message, level=level)
    return NotificationManager().notify_escalation(
        project_name=project_name or "Unknown",
        task_title=task_title or "Unknown",
        reason=reason or "Escalation required",
        risk_flags=risk_flags or []
    )
