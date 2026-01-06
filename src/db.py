"""
Agent-OS v3 Database Connection Module

Following million-step methodology:
- All database operations are transactional
- Connections are pooled and managed
- Errors are explicit, never swallowed
"""

import os
from dotenv import load_dotenv; load_dotenv("/opt/agent-os-v3/.env")
import json
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import Optional, Dict, Any, List

# Connection pool
_pool: Optional[pool.ThreadedConnectionPool] = None


def get_config() -> Dict[str, Any]:
    """Load database configuration."""
    config_path = os.environ.get(
        'AGENT_OS_V3_CONFIG',
        '/opt/agent-os-v3/config/settings.yaml'
    )
    
    # Simple YAML parsing (avoid external deps for bootstrap)
    config = {
        'host': os.environ.get('DB_HOST', 'localhost'),
        'port': int(os.environ.get('DB_PORT', '5432')),
        'name': os.environ.get('DB_NAME', 'agent_os_v3'),
        'user': os.environ.get('DB_USER', 'maestro'),
        'password': os.environ.get('DB_PASSWORD', 'maestro_secret_2024'),
    }
    
    return config


def init_pool(min_conn: int = 2, max_conn: int = 10):
    """Initialize the connection pool."""
    global _pool
    
    if _pool is not None:
        return
    
    config = get_config()
    
    _pool = pool.ThreadedConnectionPool(
        min_conn,
        max_conn,
        host=config['host'],
        port=config['port'],
        database=config['name'],
        user=config['user'],
        password=config['password']
    )


def get_pool() -> pool.ThreadedConnectionPool:
    """Get the connection pool, initializing if needed."""
    global _pool
    
    if _pool is None:
        init_pool()
    
    return _pool


@contextmanager
def get_connection():
    """
    Get a database connection from the pool using context manager pattern.
    
    This function implements the context manager protocol to safely acquire and
    release database connections from the ThreadedConnectionPool. Connections are
    automatically returned to the pool when the context exits, even if an exception
    occurs.
    
    Connection Pooling:
        - Connections are managed by psycopg2.pool.ThreadedConnectionPool
        - Pool is initialized lazily on first use with min=2, max=10 connections
        - Connections are thread-safe and automatically recycled
        - Pool prevents connection exhaustion and manages lifecycle
    
    When to Use:
        - Use this when you need direct connection control for transactions
        - Prefer get_cursor() for simple queries with auto-commit
        - Prefer transaction() for multi-statement transactions with rollback
    
    Yields:
        psycopg2.extensions.connection: A database connection from the pool
    
    Usage:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                conn.commit()  # Manual commit required
    """
    pool = get_pool()
    conn = pool.getconn()
    
    try:
        yield conn
    finally:
        pool.putconn(conn)


@contextmanager
def get_cursor(dict_cursor: bool = True):
    """
    Get a cursor with automatic connection management.
    
    Usage:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM tasks")
            rows = cur.fetchall()
    """
    with get_connection() as conn:
        cursor_factory = RealDictCursor if dict_cursor else None
        with conn.cursor(cursor_factory=cursor_factory) as cur:
            yield cur
        conn.commit()


@contextmanager
def transaction():
    """
    Execute multiple operations in a transaction.
    Rolls back on any exception.
    
    Usage:
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO ...")
                cur.execute("UPDATE ...")
    """
    with get_connection() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def execute(sql: str, params: tuple = None) -> None:
    """Execute a SQL statement."""
    with get_cursor(dict_cursor=False) as cur:
        cur.execute(sql, params)


def query_one(sql: str, params: tuple = None) -> Optional[Dict[str, Any]]:
    """Execute a query and return one row as dict."""
    with get_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def query_all(sql: str, params: tuple = None) -> List[Dict[str, Any]]:
    """Execute a query and return all rows as dicts."""
    with get_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def insert_returning(
    table: str,
    data: Dict[str, Any],
    returning: str = 'id'
) -> Any:
    """
    Insert a row and return a column value.
    
    Args:
        table: Table name
        data: Dict of column -> value
        returning: Column to return (default: 'id')
    
    Returns:
        The value of the returning column
    """
    columns = list(data.keys())
    placeholders = ['%s'] * len(columns)
    
    sql = f"""
        INSERT INTO {table} ({', '.join(columns)})
        VALUES ({', '.join(placeholders)})
        RETURNING {returning}
    """
    
    with get_cursor() as cur:
        cur.execute(sql, tuple(data.values()))
        result = cur.fetchone()
        return result[returning] if result else None


def update(
    table: str,
    data: Dict[str, Any],
    where: Dict[str, Any]
) -> int:
    """
    Update rows in a table.
    
    Args:
        table: Table name
        data: Dict of column -> new value
        where: Dict of column -> value for WHERE clause
    
    Returns:
        Number of rows updated
    """
    set_clause = ', '.join([f"{k} = %s" for k in data.keys()])
    where_clause = ' AND '.join([f"{k} = %s" for k in where.keys()])
    
    sql = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
    
    params = tuple(data.values()) + tuple(where.values())
    
    with get_cursor(dict_cursor=False) as cur:
        cur.execute(sql, params)
        return cur.rowcount


def close_pool():
    """Close all connections in the pool."""
    global _pool
    
    if _pool is not None:
        _pool.closeall()
        _pool = None


# Test connection on import (only if running directly)
if __name__ == '__main__':
    print("Testing database connection...")
    try:
        with get_cursor() as cur:
            cur.execute("SELECT COUNT(*) as count FROM checkpoints")
            result = cur.fetchone()
            print(f"Connected! Checkpoints table has {result['count']} rows")
    except Exception as e:
        print(f"Connection failed: {e}")
