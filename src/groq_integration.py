"""
Agent-OS v3 Groq Integration Module

Integrates Groq-powered validators for:
- Schema validation (Llama 3.1 8B) - 99% cheaper than Claude
- Uncertainty detection (Llama 3.3 70B) - 85% cheaper than Claude

Now includes cost tracking integration.
"""

import json
import subprocess
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass

# Path to the Groq validators script
GROQ_VALIDATORS_PATH = "/opt/agent-os/groq_validators.py"


@dataclass
class GroqValidationResult:
    """Result from Groq validation."""
    success: bool
    valid: bool
    errors: List[Dict[str, Any]]
    latency_ms: int
    cost_usd: float
    model: str
    input_tokens: int
    output_tokens: int
    raw_response: Dict[str, Any]


@dataclass 
class GroqUncertaintyResult:
    """Result from Groq uncertainty detection."""
    success: bool
    has_uncertainty: bool
    should_halt: bool
    confidence_score: float
    signals: List[Dict[str, Any]]
    summary: str
    latency_ms: int
    cost_usd: float
    model: str
    input_tokens: int
    output_tokens: int
    raw_response: Dict[str, Any]


def call_groq_validator(command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Call the Groq validators script."""
    try:
        result = subprocess.run(
            ["python3", GROQ_VALIDATORS_PATH, command, json.dumps(payload)],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return {
                "success": False,
                "error": result.stderr or "Unknown error",
                "meta": {"latency_ms": 0, "cost_estimate": {"cost_usd": 0}, "tokens": {"input": 0, "output": 0}}
            }
        
        return json.loads(result.stdout)
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Groq validator timeout (30s)",
            "meta": {"latency_ms": 30000, "cost_estimate": {"cost_usd": 0}, "tokens": {"input": 0, "output": 0}}
        }
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Invalid JSON response: {e}",
            "meta": {"latency_ms": 0, "cost_estimate": {"cost_usd": 0}, "tokens": {"input": 0, "output": 0}}
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "meta": {"latency_ms": 0, "cost_estimate": {"cost_usd": 0}, "tokens": {"input": 0, "output": 0}}
        }


def _track_groq_usage(
    operation: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    cost_usd: float,
    success: bool,
    project_id: Optional[str] = None,
    task_id: Optional[str] = None
):
    """Track Groq API usage in the database."""
    try:
        from cost_tracker import track_usage
        track_usage(
            provider="groq",
            model=model,
            operation=operation,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            success=success,
            project_id=project_id,
            task_id=task_id
        )
    except Exception as e:
        # Don't fail if tracking fails
        pass


def validate_schema(
    schema: Dict[str, Any], 
    data: Dict[str, Any],
    project_id: Optional[str] = None,
    task_id: Optional[str] = None
) -> GroqValidationResult:
    """
    Validate data against a JSON schema using Groq's Llama 3.1 8B.
    
    Cost: ~$0.00001 per call
    Latency: ~260ms
    """
    response = call_groq_validator("schema-validate", {
        "schema": schema,
        "data": data
    })
    
    meta = response.get("meta", {})
    validation = response.get("validation", {})
    tokens = meta.get("tokens", {})
    
    input_tokens = tokens.get("input", 0)
    output_tokens = tokens.get("output", 0)
    latency_ms = meta.get("latency_ms", 0)
    cost_usd = meta.get("cost_estimate", {}).get("cost_usd", 0)
    model = meta.get("model", "llama-3.1-8b-instant")
    success = response.get("success", False)
    
    # Track usage
    _track_groq_usage(
        operation="schema_validate",
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        success=success,
        project_id=project_id,
        task_id=task_id
    )
    
    return GroqValidationResult(
        success=success,
        valid=validation.get("valid", False),
        errors=validation.get("errors", []),
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        raw_response=response
    )


def detect_uncertainty(
    content: str,
    context: str = "",
    task_type: str = "general",
    project_id: Optional[str] = None,
    task_id: Optional[str] = None
) -> GroqUncertaintyResult:
    """
    Detect uncertainty in LLM output using Groq's Llama 3.3 70B.
    
    Cost: ~$0.00015 per call
    Latency: ~400ms
    """
    response = call_groq_validator("uncertainty-detect", {
        "content": content,
        "context": context,
        "task_type": task_type
    })
    
    meta = response.get("meta", {})
    detection = response.get("detection", {})
    tokens = meta.get("tokens", {})
    
    input_tokens = tokens.get("input", 0)
    output_tokens = tokens.get("output", 0)
    latency_ms = meta.get("latency_ms", 0)
    cost_usd = meta.get("cost_estimate", {}).get("cost_usd", 0)
    model = meta.get("model", "llama-3.3-70b-versatile")
    success = response.get("success", False)
    
    # Track usage
    _track_groq_usage(
        operation="uncertainty_detect",
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        success=success,
        project_id=project_id,
        task_id=task_id
    )
    
    return GroqUncertaintyResult(
        success=success,
        has_uncertainty=detection.get("has_uncertainty", False),
        should_halt=detection.get("should_halt", False),
        confidence_score=detection.get("confidence_score", 1.0),
        signals=detection.get("signals", []),
        summary=detection.get("summary", ""),
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        raw_response=response
    )


# Predefined schemas for common Agent-OS outputs
DRAFT_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["files_to_create", "files_to_modify", "confidence_score"],
    "properties": {
        "files_to_create": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["path", "content"],
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "purpose": {"type": "string"}
                }
            }
        },
        "files_to_modify": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["path", "diff"],
                "properties": {
                    "path": {"type": "string"},
                    "original_hash": {"type": "string"},
                    "diff": {"type": "string"},
                    "purpose": {"type": "string"}
                }
            }
        },
        "confidence_score": {
            "type": "number",
            "minimum": 0,
            "maximum": 1
        },
        "uncertainty_flags": {
            "type": "array",
            "items": {"type": "string"}
        },
        "reasoning": {"type": "string"},
        "estimated_complexity": {
            "type": "string",
            "enum": ["trivial", "simple", "moderate", "complex", "expert"]
        }
    }
}

VERIFICATION_RESULT_SCHEMA = {
    "type": "object",
    "required": ["decision", "checks_performed", "verifier_confidence"],
    "properties": {
        "decision": {
            "type": "string",
            "enum": ["approved", "rejected", "revision_required", "escalate_to_compliance"]
        },
        "checks_performed": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["check_name", "passed"],
                "properties": {
                    "check_name": {"type": "string"},
                    "passed": {"type": "boolean"},
                    "details": {"type": "string"}
                }
            }
        },
        "issues_found": {"type": "array"},
        "risk_flags": {"type": "array"},
        "verifier_confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1
        }
    }
}


def validate_draft_output(
    draft: Dict[str, Any],
    project_id: Optional[str] = None,
    task_id: Optional[str] = None
) -> GroqValidationResult:
    """Validate a draft proposal against the expected schema."""
    return validate_schema(DRAFT_OUTPUT_SCHEMA, draft, project_id, task_id)


def validate_verification_result(
    result: Dict[str, Any],
    project_id: Optional[str] = None,
    task_id: Optional[str] = None
) -> GroqValidationResult:
    """Validate a verification result against the expected schema."""
    return validate_schema(VERIFICATION_RESULT_SCHEMA, result, project_id, task_id)


if __name__ == "__main__":
    print("Testing Groq Integration with Cost Tracking...")
    
    # Test schema validation
    print("\n1. Testing schema validation...")
    result = validate_schema(
        {"type": "object", "required": ["name"]},
        {"name": "Test"}
    )
    print(f"   Valid: {result.valid}, Latency: {result.latency_ms}ms, Cost: ${result.cost_usd:.6f}")
    
    # Test uncertainty detection
    print("\n2. Testing uncertainty detection...")
    result = detect_uncertainty(
        "I think this might work.",
        context="Code review",
        task_type="implementation"
    )
    print(f"   Uncertain: {result.has_uncertainty}, Latency: {result.latency_ms}ms")
    
    # Show cost report
    print("\n3. Checking tracked costs...")
    try:
        from cost_tracker import format_cost_report
        print(format_cost_report())
    except Exception as e:
        print(f"   Could not load cost report: {e}")
