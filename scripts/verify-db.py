#!/usr/bin/env python3
import os
import sys
os.environ.setdefault('DB_HOST', '172.23.0.2')
os.environ.setdefault('DB_NAME', 'agent_os_v3')
os.environ.setdefault('DB_USER', 'maestro')
os.environ.setdefault('DB_PASSWORD', 'maestro_secret_2024')
sys.path.insert(0, '/opt/agent-os-v3/src')
from db import query_one
result = query_one('SELECT COUNT(*) as count FROM checkpoints')
count = result['count']
print(f'Checkpoints: {count}')
print('DB connection OK')

