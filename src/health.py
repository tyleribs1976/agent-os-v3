#!/usr/bin/env python3
"""
Agent-OS v3 Health Check Module

Provides comprehensive health checking for the Agent-OS v3 system.
Checks PostgreSQL connectivity, disk space, and orchestrator responsiveness.

Following million-step methodology:
- All checks are explicit and measurable
- No silent failures
- Clear status reporting
"""

import os
import json
import psutil
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from db import query_one


class HealthChecker:
    """
    Comprehensive health checker for Agent-OS v3.
    
    Performs checks for:
    - PostgreSQL database connectivity
    - Disk space on /opt/agent-os-v3
    - Orchestrator process responsiveness
    """
    
    def __init__(self, disk_warning_threshold: float = 0.8, disk_critical_threshold: float = 0.9):
        """
        Initialize health checker.
        
        Args:
            disk_warning_threshold: Warn when disk usage exceeds this percentage (0.0-1.0)
            disk_critical_threshold: Critical when disk usage exceeds this percentage (0.0-1.0)
        """
        self.disk_warning_threshold = disk_warning_threshold
        self.disk_critical_threshold = disk_critical_threshold
        self.agent_os_path = Path('/opt/agent-os-v3')
    
    def check_postgresql(self) -> Dict[str, Any]:
        """
        Check PostgreSQL database connectivity.
        
        Returns:
            Dict with name, status ('healthy'|'unhealthy'), and message
        """
        try:
            # Simple connectivity test using existing db module
            result = query_one("SELECT 1 as test_value, NOW() as current_time")
            
            if result and result.get('test_value') == 1:
                return {
                    'name': 'postgresql',
                    'status': 'healthy',
                    'message': f"Connected successfully at {result.get('current_time')}"
                }
            else:
                return {
                    'name': 'postgresql',
                    'status': 'unhealthy',
                    'message': 'Query executed but returned unexpected result'
                }
                
        except Exception as e:
            return {
                'name': 'postgresql',
                'status': 'unhealthy',
                'message': f'Database connection failed: {str(e)}'
            }
    
    def check_disk_space(self) -> Dict[str, Any]:
        """
        Check disk space on /opt/agent-os-v3.
        
        Returns:
            Dict with name, status, and message including usage details
        """
        try:
            if not self.agent_os_path.exists():
                return {
                    'name': 'disk_space',
                    'status': 'unhealthy',
                    'message': '/opt/agent-os-v3 directory does not exist'
                }
            
            # Get disk usage for the mount point containing /opt/agent-os-v3
            usage = shutil.disk_usage(self.agent_os_path)
            
            total_gb = usage.total / (1024**3)
            used_gb = usage.used / (1024**3)
            free_gb = usage.free / (1024**3)
            usage_percent = usage.used / usage.total
            
            if usage_percent >= self.disk_critical_threshold:
                status = 'unhealthy'
                level = 'CRITICAL'
            elif usage_percent >= self.disk_warning_threshold:
                status = 'unhealthy'
                level = 'WARNING'
            else:
                status = 'healthy'
                level = 'OK'
            
            message = (
                f"{level}: {usage_percent:.1%} used "
                f"({used_gb:.1f}GB used, {free_gb:.1f}GB free of {total_gb:.1f}GB total)"
            )
            
            return {
                'name': 'disk_space',
                'status': status,
                'message': message
            }
            
        except Exception as e:
            return {
                'name': 'disk_space',
                'status': 'unhealthy',
                'message': f'Failed to check disk space: {str(e)}'
            }
    
    def check_orchestrator(self) -> Dict[str, Any]:
        """
        Check orchestrator process responsiveness.
        
        Returns:
            Dict with name, status, and message about orchestrator state
        """
        try:
            # Look for orchestrator processes
            orchestrator_processes = []
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    # Check if this is an orchestrator process
                    if proc.info['cmdline']:
                        cmdline_str = ' '.join(proc.info['cmdline'])
                        if 'orchestrator.py' in cmdline_str or 'orchestrator' in proc.info['name']:
                            orchestrator_processes.append({
                                'pid': proc.info['pid'],
                                'name': proc.info['name'],
                                'cmdline': cmdline_str
                            })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if orchestrator_processes:
                return {
                    'name': 'orchestrator',
                    'status': 'healthy',
                    'message': f'Found {len(orchestrator_processes)} orchestrator process(es) running'
                }
            else:
                return {
                    'name': 'orchestrator',
                    'status': 'unhealthy',
                    'message': 'No orchestrator processes found'
                }
                
        except Exception as e:
            return {
                'name': 'orchestrator',
                'status': 'unhealthy',
                'message': f'Failed to check orchestrator: {str(e)}'
            }
    
    def run_all_checks(self) -> Dict[str, Any]:
        """
        Run all health checks and return comprehensive status.
        
        Returns:
            Dict with overall health status, individual check results, and timestamp
        """
        checks = [
            self.check_postgresql(),
            self.check_disk_space(),
            self.check_orchestrator()
        ]
        
        # Overall health is healthy only if ALL checks pass
        overall_healthy = all(check['status'] == 'healthy' for check in checks)
        
        return {
            'healthy': overall_healthy,
            'checks': checks,
            'timestamp': datetime.utcnow().isoformat()
        }


if __name__ == '__main__':
    """
    Command-line interface for health checking.
    
    Usage:
        python src/health.py
    """
    checker = HealthChecker()
    result = checker.run_all_checks()
    
    # Pretty print the results
    print(json.dumps(result, indent=2))
    
    # Exit with error code if unhealthy
    if not result['healthy']:
        exit(1)
