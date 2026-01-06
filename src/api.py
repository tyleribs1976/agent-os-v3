"""
Agent-OS v3 Flask API

Provides REST endpoints for health checks and system status.

Endpoints:
- GET /health: Health check endpoint
- GET /status: Detailed system status
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, jsonify, request
from db import query_one, query_all

app = Flask(__name__)


@app.route('/health', methods=['GET'])
def health():
    """
    Health check endpoint.
    
    Returns:
        JSON response with status 'ok' if system is healthy
    """
    try:
        # Test database connectivity
        result = query_one("SELECT 1 as test")
        if result and result.get('test') == 1:
            return jsonify({
                'status': 'ok',
                'timestamp': datetime.utcnow().isoformat(),
                'service': 'agent-os-v3'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Database query failed',
                'timestamp': datetime.utcnow().isoformat()
            }), 503
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 503


@app.route('/status', methods=['GET'])
def status():
    """
    System status endpoint.
    
    Returns detailed status including:
    - Task counts by status
    - Recent checkpoint activity
    - System health metrics
    """
    try:
        # Get task counts by status
        task_counts = query_all(
            "SELECT status, COUNT(*) as count FROM tasks GROUP BY status"
        )
        
        # Get recent checkpoints (last 10)
        recent_checkpoints = query_all(
            """
            SELECT phase, step_name, status, created_at, completed_at
            FROM checkpoints
            ORDER BY created_at DESC
            LIMIT 10
            """
        )
        
        # Get active tasks
        active_tasks = query_all(
            """
            SELECT id, title, task_type, status, current_phase, created_at
            FROM tasks
            WHERE status IN ('running', 'pending', 'queued')
            ORDER BY created_at DESC
            LIMIT 5
            """
        )
        
        # Calculate success rate
        success_rate_result = query_one(
            """
            SELECT 
                COUNT(CASE WHEN status='complete' THEN 1 END) as completed,
                COUNT(*) as total,
                ROUND(
                    COUNT(CASE WHEN status='complete' THEN 1 END) * 100.0 / 
                    NULLIF(COUNT(*), 0), 
                    1
                ) as success_rate
            FROM tasks
            """
        )
        
        return jsonify({
            'status': 'ok',
            'timestamp': datetime.utcnow().isoformat(),
            'task_counts': {row['status']: row['count'] for row in task_counts},
            'success_rate': float(success_rate_result['success_rate']) if success_rate_result['success_rate'] else 0.0,
            'active_tasks': [
                {
                    'id': str(task['id']),
                    'title': task['title'],
                    'type': task['task_type'],
                    'status': task['status'],
                    'phase': task['current_phase'],
                    'created_at': task['created_at'].isoformat() if task['created_at'] else None
                }
                for task in active_tasks
            ],
            'recent_checkpoints': [
                {
                    'phase': cp['phase'],
                    'step': cp['step_name'],
                    'status': cp['status'],
                    'created_at': cp['created_at'].isoformat() if cp['created_at'] else None,
                    'completed_at': cp['completed_at'].isoformat() if cp['completed_at'] else None
                }
                for cp in recent_checkpoints
            ]
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({
        'status': 'error',
        'message': 'Endpoint not found',
        'timestamp': datetime.utcnow().isoformat()
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return jsonify({
        'status': 'error',
        'message': 'Internal server error',
        'timestamp': datetime.utcnow().isoformat()
    }), 500


if __name__ == '__main__':
    # Development server - not for production
    port = int(os.environ.get('API_PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
