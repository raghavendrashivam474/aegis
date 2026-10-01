"""
Tests for Aegis PostgreSQL Connection Pooling and Resilience (P1.S7).
"""

from unittest.mock import MagicMock, patch

import psycopg
import pytest
from psycopg_pool import PoolTimeout

from apps.backend.postgres_adapter import (
    PostgresConnectionPool,
    PostgresDeviceRegistry,
    PostgresTelemetryRepository,
)


def test_pool_initialization_and_stats():
    """Verify pool constructor parameters and initial statistics."""
    with patch("apps.backend.postgres_adapter.ConnectionPool") as mock_cp:
        mock_instance = MagicMock()
        mock_instance.closed = False
        mock_cp.return_value = mock_instance

        pool = PostgresConnectionPool(
            database_url="postgresql://user:pass@localhost:5432/db",
            min_size=2,
            max_size=5,
            timeout=3.0,
            open_immediately=False,
        )

        stats = pool.stats
        assert stats["min_size"] == 2
        assert stats["max_size"] == 5
        assert stats["timeout"] == 3.0
        assert stats["closed"] is False

        pool.close()
        mock_instance.close.assert_called_once()


def test_pool_connection_checkout_and_release():
    """Verify connection is acquired from pool context manager."""
    with patch("apps.backend.postgres_adapter.ConnectionPool") as mock_cp:
        mock_instance = MagicMock()
        mock_conn = MagicMock()
        mock_instance.connection.return_value.__enter__.return_value = mock_conn
        mock_cp.return_value = mock_instance

        pool = PostgresConnectionPool("postgresql://fake:5432/db")
        with pool.connection() as conn:
            assert conn == mock_conn

        mock_instance.connection.assert_called_once()


def test_pool_timeout_handling():
    """Verify PoolTimeout is raised and logged cleanly when pool is exhausted."""
    with patch("apps.backend.postgres_adapter.ConnectionPool") as mock_cp:
        mock_instance = MagicMock()
        mock_instance.connection.side_effect = PoolTimeout("Pool exhausted")
        mock_cp.return_value = mock_instance

        pool = PostgresConnectionPool("postgresql://fake:5432/db", timeout=1.0)
        with pytest.raises(PoolTimeout):
            with pool.connection():
                pass


def test_pool_health_check_success_and_failure():
    """Verify health check logic returns True on success and False on operational failure."""
    with patch("apps.backend.postgres_adapter.ConnectionPool") as mock_cp:
        mock_instance = MagicMock()
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (1,)
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_instance.connection.return_value.__enter__.return_value = mock_conn
        mock_cp.return_value = mock_instance

        pool = PostgresConnectionPool("postgresql://fake:5432/db")
        assert pool.check_health() is True

        # Simulate DB down
        mock_instance.connection.side_effect = psycopg.OperationalError("Connection refused")
        assert pool.check_health() is False


def test_adapters_accept_shared_pool():
    """Verify PostgresDeviceRegistry and PostgresTelemetryRepository can share an external pool."""
    with patch("apps.backend.postgres_adapter.ConnectionPool") as mock_cp:
        mock_instance = MagicMock()
        mock_cp.return_value = mock_instance

        shared_pool = PostgresConnectionPool("postgresql://fake:5432/db")
        registry = PostgresDeviceRegistry(pool=shared_pool)
        repo = PostgresTelemetryRepository(pool=shared_pool)

        assert registry._pool == shared_pool
        assert repo._pool == shared_pool
        assert registry._owns_pool is False
        assert repo._owns_pool is False

        # Closing registry does not close shared pool
        registry.close()
        mock_instance.close.assert_not_called()

        shared_pool.close()
        mock_instance.close.assert_called_once()
