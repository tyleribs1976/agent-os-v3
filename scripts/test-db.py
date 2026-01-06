import sys
sys.path.insert(0, "/opt/agent-os-v3/src")
from db import query_one
result = query_one("SELECT 1 as test")
print(f"DB test: {result}")
