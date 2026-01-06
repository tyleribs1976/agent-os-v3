"""
Agent-OS v3 API Cost Tracker

Centralized tracking of all API usage and costs across providers:
- Anthropic (Claude) - Drafter, Verifier roles
- Groq - Schema validation, Uncertainty detection

Pricing (as of Jan 2026):
- Claude Sonnet 4: $3/1M input, $15/1M output
- Claude Opus 4.5: $15/1M input, $75/1M output
- Groq Llama 3.1 8B: $0.05/1M input, $0.08/1M output
- Groq Llama 3.3 70B: $0.59/1M input, $0.79/1M output
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).parent))

from db import insert_returning, query_one, query_all, execute

# Import Json adapter for psycopg2
try:
    from psycopg2.extras import Json
except ImportError:
    Json = lambda x: json.dumps(x)


# Pricing per million tokens (USD)
PRICING = {
    "anthropic": {
        "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
        "claude-opus-4-5-20251101": {"input": 15.00, "output": 75.00},
        "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
        "default": {"input": 3.00, "output": 15.00}
    },
    "groq": {
        "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
        "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
        "llama-3.1-70b-versatile": {"input": 0.59, "output": 0.79},
        "default": {"input": 0.59, "output": 0.79}
    },
    "openai": {
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        "gpt-4o": {"input": 5.00, "output": 15.00},
        "default": {"input": 5.00, "output": 15.00}
    }
}


def calculate_cost(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int
) -> float:
    """Calculate cost in USD for given token usage."""
    provider_pricing = PRICING.get(provider, PRICING["anthropic"])
    model_pricing = provider_pricing.get(model, provider_pricing["default"])
    
    input_cost = (input_tokens / 1_000_000) * model_pricing["input"]
    output_cost = (output_tokens / 1_000_000) * model_pricing["output"]
    
    return round(input_cost + output_cost, 8)


def track_usage(
    provider: str,
    model: str,
    operation: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: Optional[float] = None,
    latency_ms: int = 0,
    success: bool = True,
    project_id: Optional[str] = None,
    task_id: Optional[str] = None,
    checkpoint_id: Optional[int] = None,
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Optional[int]:
    """Track API usage in the database."""
    if cost_usd is None:
        cost_usd = calculate_cost(provider, model, input_tokens, output_tokens)
    
    try:
        # Use raw SQL to handle JSONB properly
        result = query_one("""
            INSERT INTO api_usage 
            (provider, model, operation, input_tokens, output_tokens, cost_usd, 
             latency_ms, success, project_id, task_id, checkpoint_id, error_message, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id
        """, (
            provider, model, operation, input_tokens, output_tokens, cost_usd,
            latency_ms, success, project_id, task_id, checkpoint_id, error_message,
            json.dumps(metadata or {})
        ))
        return result.get('id') if result else None
    except Exception as e:
        print(f"Warning: Failed to track API usage: {e}")
        return None


def get_daily_costs(days: int = 7) -> List[Dict[str, Any]]:
    """Get daily cost summary for the last N days."""
    return query_all("""
        SELECT * FROM daily_costs 
        WHERE date >= CURRENT_DATE - INTERVAL '%s days'
        ORDER BY date DESC, provider
    """, (days,)) or []


def get_project_costs(project_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get cost summary by project."""
    if project_id:
        return query_all("""
            SELECT * FROM project_costs WHERE project_id = %s
        """, (project_id,)) or []
    return query_all("SELECT * FROM project_costs") or []


def get_monthly_costs(months: int = 3) -> List[Dict[str, Any]]:
    """Get monthly cost summary."""
    return query_all("""
        SELECT * FROM monthly_costs 
        WHERE month >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '%s months')
        ORDER BY month DESC, total_cost_usd DESC
    """, (months,)) or []


def get_operation_costs() -> List[Dict[str, Any]]:
    """Get cost summary by operation type."""
    return query_all("SELECT * FROM operation_costs") or []


def get_today_summary() -> Dict[str, Any]:
    """Get summary of today's API usage."""
    result = query_one("""
        SELECT 
            COUNT(*) as total_calls,
            COALESCE(SUM(input_tokens), 0) as total_input_tokens,
            COALESCE(SUM(output_tokens), 0) as total_output_tokens,
            COALESCE(SUM(total_tokens), 0) as total_tokens,
            COALESCE(SUM(cost_usd), 0) as total_cost_usd,
            COALESCE(AVG(latency_ms)::INTEGER, 0) as avg_latency_ms,
            SUM(CASE WHEN success THEN 1 ELSE 0 END) as success_count,
            SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as error_count
        FROM api_usage 
        WHERE DATE(timestamp) = CURRENT_DATE
    """)
    return result or {
        "total_calls": 0,
        "total_tokens": 0,
        "total_cost_usd": 0,
        "avg_latency_ms": 0
    }


def get_total_costs() -> Dict[str, Any]:
    """Get all-time cost summary."""
    result = query_one("""
        SELECT 
            COUNT(*) as total_calls,
            COALESCE(SUM(input_tokens), 0) as total_input_tokens,
            COALESCE(SUM(output_tokens), 0) as total_output_tokens,
            COALESCE(SUM(total_tokens), 0) as total_tokens,
            COALESCE(SUM(cost_usd), 0) as total_cost_usd,
            MIN(timestamp) as first_call,
            MAX(timestamp) as last_call
        FROM api_usage
    """)
    return result or {"total_calls": 0, "total_cost_usd": 0}


def get_provider_breakdown() -> List[Dict[str, Any]]:
    """Get cost breakdown by provider."""
    return query_all("""
        SELECT 
            provider,
            COUNT(*) as call_count,
            COALESCE(SUM(total_tokens), 0) as total_tokens,
            COALESCE(SUM(cost_usd), 0) as total_cost_usd,
            COALESCE(AVG(latency_ms)::INTEGER, 0) as avg_latency_ms
        FROM api_usage
        GROUP BY provider
        ORDER BY total_cost_usd DESC
    """) or []


def format_cost_report(include_details: bool = False) -> str:
    """Generate a formatted cost report string."""
    today = get_today_summary()
    total = get_total_costs()
    providers = get_provider_breakdown()
    
    def safe_int(val):
        return int(val) if val else 0
    
    def safe_float(val):
        return float(val) if val else 0.0
    
    report = "💰 API Cost Report\n"
    report += "=" * 30 + "\n\n"
    
    # Today's summary
    report += "📅 Today:\n"
    report += f"   Calls: {safe_int(today.get('total_calls'))}\n"
    report += f"   Tokens: {safe_int(today.get('total_tokens')):,}\n"
    report += f"   Cost: ${safe_float(today.get('total_cost_usd')):.4f}\n\n"
    
    # All-time summary
    report += "📊 All Time:\n"
    report += f"   Calls: {safe_int(total.get('total_calls')):,}\n"
    report += f"   Tokens: {safe_int(total.get('total_tokens')):,}\n"
    report += f"   Cost: ${safe_float(total.get('total_cost_usd')):.4f}\n\n"
    
    # Provider breakdown
    if providers:
        report += "🏢 By Provider:\n"
        for p in providers:
            report += f"   {p['provider']}: ${safe_float(p['total_cost_usd']):.4f} ({p['call_count']} calls)\n"
    
    if include_details:
        daily = get_daily_costs(7)
        if daily:
            report += "\n📆 Last 7 Days:\n"
            for d in daily[:7]:
                report += f"   {d['date']}: ${safe_float(d['total_cost_usd']):.4f} ({d['call_count']} calls)\n"
    
    return report


# Convenience functions for common operations
def track_claude_draft(
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    model: str = "claude-sonnet-4-20250514",
    project_id: Optional[str] = None,
    task_id: Optional[str] = None,
    success: bool = True,
    error_message: Optional[str] = None
) -> Optional[int]:
    """Track a Claude drafting operation."""
    return track_usage(
        provider="anthropic",
        model=model,
        operation="draft",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        project_id=project_id,
        task_id=task_id,
        success=success,
        error_message=error_message
    )


def track_claude_verify(
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    model: str = "claude-sonnet-4-20250514",
    project_id: Optional[str] = None,
    task_id: Optional[str] = None,
    success: bool = True,
    error_message: Optional[str] = None
) -> Optional[int]:
    """Track a Claude verification operation."""
    return track_usage(
        provider="anthropic",
        model=model,
        operation="verify",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        project_id=project_id,
        task_id=task_id,
        success=success,
        error_message=error_message
    )


def track_groq_schema(
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    cost_usd: float,
    model: str = "llama-3.1-8b-instant",
    project_id: Optional[str] = None,
    task_id: Optional[str] = None,
    success: bool = True
) -> Optional[int]:
    """Track a Groq schema validation operation."""
    return track_usage(
        provider="groq",
        model=model,
        operation="schema_validate",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        project_id=project_id,
        task_id=task_id,
        success=success
    )


def track_groq_uncertainty(
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    cost_usd: float,
    model: str = "llama-3.3-70b-versatile",
    project_id: Optional[str] = None,
    task_id: Optional[str] = None,
    success: bool = True
) -> Optional[int]:
    """Track a Groq uncertainty detection operation."""
    return track_usage(
        provider="groq",
        model=model,
        operation="uncertainty_detect",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        project_id=project_id,
        task_id=task_id,
        success=success
    )


if __name__ == "__main__":
    print("Testing Cost Tracker...")
    
    # Test cost calculation
    print("\n1. Cost calculations:")
    print(f"   Claude Sonnet 1K in/1K out: ${calculate_cost('anthropic', 'claude-sonnet-4-20250514', 1000, 1000):.6f}")
    print(f"   Groq 8B 1K in/1K out: ${calculate_cost('groq', 'llama-3.1-8b-instant', 1000, 1000):.8f}")
    print(f"   Groq 70B 1K in/1K out: ${calculate_cost('groq', 'llama-3.3-70b-versatile', 1000, 1000):.6f}")
    
    # Test tracking
    print("\n2. Testing track_usage...")
    record_id = track_usage(
        provider="groq",
        model="llama-3.1-8b-instant",
        operation="test",
        input_tokens=100,
        output_tokens=50,
        latency_ms=250,
        success=True,
        metadata={"test": True}
    )
    print(f"   Created record ID: {record_id}")
    
    # Test reports
    print("\n3. Cost Report:")
    print(format_cost_report())
