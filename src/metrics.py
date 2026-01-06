#!/usr/bin/env python3
"""
Agent-OS v3 Metrics Module

Exports Prometheus-compatible metrics for Grafana visualization.
Following million-step methodology:
- All metrics are explicit and measurable
- No silent failures
- Clear naming conventions
"""

import json
from datetime import datetime
from typing import Dict, Any
from db import query_all, query_one


def get_task_metrics() -> Dict[str, Any]:
    """Get task completion metrics."""
    result = query_all("""
        SELECT 
            status,
            COUNT(*) as count,
            COALESCE(AVG(EXTRACT(EPOCH FROM (completed_at - created_at))), 0) as avg_duration_seconds
        FROM tasks
        GROUP BY status
    """)
    
    metrics = {
        "tasks_total": 0,
        "tasks_completed": 0,
        "tasks_failed": 0,
        "tasks_queued": 0,
        "tasks_in_progress": 0,
        "avg_completion_seconds": 0
    }
    
    for row in result:
        status = row["status"]
        count = row["count"]
        metrics["tasks_total"] += count
        
        if status == "complete":
            metrics["tasks_completed"] = count
            metrics["avg_completion_seconds"] = float(row["avg_duration_seconds"] or 0)
        elif status == "failed":
            metrics["tasks_failed"] = count
        elif status == "queued":
            metrics["tasks_queued"] = count
        elif status == "in_progress":
            metrics["tasks_in_progress"] = count
    
    return metrics


def get_checkpoint_metrics() -> Dict[str, Any]:
    """Get checkpoint metrics."""
    result = query_one("""
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status = 'complete') as completed,
            COUNT(*) FILTER (WHERE status = 'failed') as failed,
            COALESCE(AVG(pg_column_size(state_snapshot)), 0) as avg_size_bytes
        FROM checkpoints
    """)
    
    return {
        "checkpoints_total": result["total"] if result else 0,
        "checkpoints_completed": result["completed"] if result else 0,
        "checkpoints_failed": result["failed"] if result else 0,
        "checkpoint_avg_size_bytes": float(result["avg_size_bytes"] or 0) if result else 0
    }


def get_uncertainty_metrics() -> Dict[str, Any]:
    """Get uncertainty halt metrics."""
    result = query_all("""
        SELECT 
            signal_type,
            COUNT(*) as count
        FROM uncertainty_signals
        WHERE created_at > NOW() - INTERVAL '24 hours'
        GROUP BY signal_type
    """)
    
    metrics = {
        "uncertainty_halts_24h": 0,
        "halts_by_type": {}
    }
    
    for row in result:
        count = row["count"]
        metrics["uncertainty_halts_24h"] += count
        metrics["halts_by_type"][row["signal_type"]] = count
    
    return metrics


def get_verification_metrics() -> Dict[str, Any]:
    """Get verification rejection rate."""
    result = query_one("""
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE decision = 'approved') as approved,
            COUNT(*) FILTER (WHERE decision = 'rejected') as rejected
        FROM verifications
        WHERE created_at > NOW() - INTERVAL '7 days'
    """)
    
    total = result["total"] if result else 0
    rejected = result["rejected"] if result else 0
    
    return {
        "verifications_total_7d": total,
        "verifications_approved_7d": result["approved"] if result else 0,
        "verifications_rejected_7d": rejected,
        "verification_rejection_rate": (rejected / total * 100) if total > 0 else 0
    }


def get_all_metrics() -> Dict[str, Any]:
    """Get all metrics for export."""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "tasks": get_task_metrics(),
        "checkpoints": get_checkpoint_metrics(),
        "uncertainty": get_uncertainty_metrics(),
        "verification": get_verification_metrics()
    }


def export_prometheus() -> str:
    """Export metrics in Prometheus format."""
    metrics = get_all_metrics()
    lines = []
    
    # Task metrics
    lines.append(f"agent_os_v3_tasks_total {metrics['tasks']['tasks_total']}")
    lines.append(f"agent_os_v3_tasks_completed {metrics['tasks']['tasks_completed']}")
    lines.append(f"agent_os_v3_tasks_failed {metrics['tasks']['tasks_failed']}")
    lines.append(f"agent_os_v3_tasks_queued {metrics['tasks']['tasks_queued']}")
    lines.append(f"agent_os_v3_tasks_in_progress {metrics['tasks']['tasks_in_progress']}")
    lines.append(f"agent_os_v3_task_avg_duration_seconds {metrics['tasks']['avg_completion_seconds']}")
    
    # Checkpoint metrics
    lines.append(f"agent_os_v3_checkpoints_total {metrics['checkpoints']['checkpoints_total']}")
    lines.append(f"agent_os_v3_checkpoints_completed {metrics['checkpoints']['checkpoints_completed']}")
    lines.append(f"agent_os_v3_checkpoints_failed {metrics['checkpoints']['checkpoints_failed']}")
    lines.append(f"agent_os_v3_checkpoint_avg_size_bytes {metrics['checkpoints']['checkpoint_avg_size_bytes']}")
    
    # Uncertainty metrics
    lines.append(f"agent_os_v3_uncertainty_halts_24h {metrics['uncertainty']['uncertainty_halts_24h']}")
    
    # Verification metrics
    lines.append(f"agent_os_v3_verifications_total_7d {metrics['verification']['verifications_total_7d']}")
    lines.append(f"agent_os_v3_verification_rejection_rate {metrics['verification']['verification_rejection_rate']}")
    
    return "\n".join(lines)


if __name__ == "__main__":
    print(json.dumps(get_all_metrics(), indent=2))
