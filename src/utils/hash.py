"""Agent-OS v3 Hash Utilities

Provides functions for computing SHA256 hashes of strings and files.
Used throughout the system for integrity checking and content verification.
"""

import hashlib


def compute_sha256(content: str) -> str:
    """Compute SHA256 hash of string content.
    
    Args:
        content: String content to hash
        
    Returns:
        Hexadecimal string representation of SHA256 hash
    """
    return hashlib.sha256(content.encode()).hexdigest()


def compute_file_hash(filepath: str) -> str:
    """Compute SHA256 hash of file contents.
    
    Args:
        filepath: Path to file to hash
        
    Returns:
        Hexadecimal string representation of SHA256 hash
        
    Raises:
        FileNotFoundError: If file doesn't exist
        IOError: If file cannot be read
    """
    with open(filepath, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()
