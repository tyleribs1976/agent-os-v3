"""Agent-OS v3 Health Check Module

Provides health check endpoints and service monitoring.
Following million-step methodology: explicit, no magic.
"""

from typing import Dict, Any


# Health check endpoints for external services
HEALTH_ENDPOINTS = {
    "postgres": "localhost:5432",
    "telegram": "api.telegram.org",
    "grafana": "dash.glo.tools"
}


def get_health_endpoint(service: str) -> str:
    """
    Get health check endpoint for a service.
    
    Args:
        service: Service name (postgres, telegram, grafana)
    
    Returns:
        Health check endpoint URL/address
    
    Raises:
        KeyError: If service is not recognized
    
    Examples:
        >>> get_health_endpoint('postgres')
        'localhost:5432'
        >>> get_health_endpoint('telegram')
        'api.telegram.org'
    """
    return HEALTH_ENDPOINTS[service]


def list_health_endpoints() -> Dict[str, str]:
    """
    Get all configured health check endpoints.
    
    Returns:
        Dictionary mapping service names to their health check endpoints
    
    Examples:
        >>> endpoints = list_health_endpoints()
        >>> 'postgres' in endpoints
        True
    """
    return HEALTH_ENDPOINTS.copy()
