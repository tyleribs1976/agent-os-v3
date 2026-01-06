import sys
sys.path.insert(0, "/opt/agent-os-v3/src")
from notifications import TelegramNotifier
t = TelegramNotifier()
t.send_message("Agent-OS v3 Phase 1 modules installed successfully")
print("Notification sent")
