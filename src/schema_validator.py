import jsonschema
from typing import Dict, Any, List
from dataclasses import dataclass

@dataclass
class ValidationResult:
    valid: bool
    errors: List[Dict[str, Any]]

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
                    "diff": {"type": "string"},
                    "purpose": {"type": "string"}
                }
            }
        },
        "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
        "uncertainty_flags": {"type": "array", "items": {"type": "string"}},
        "reasoning": {"type": "string"},
        "test_suggestions": {"type": "array", "items": {"type": "string"}},
        "estimated_complexity": {"type": "string", "enum": ["trivial", "simple", "moderate", "complex", "expert"]}
    },
    "additionalProperties": True
}

def validate_schema(data, schema):
    errors = []
    try:
        jsonschema.validate(instance=data, schema=schema)
        return ValidationResult(valid=True, errors=[])
    except jsonschema.ValidationError:
        validator = jsonschema.Draft7Validator(schema)
        for error in validator.iter_errors(data):
            path = "$." + ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "$"
            errors.append({"path": path, "message": error.message})
        return ValidationResult(valid=False, errors=errors)

def validate_draft_output(draft):
    return validate_schema(draft, DRAFT_OUTPUT_SCHEMA)
