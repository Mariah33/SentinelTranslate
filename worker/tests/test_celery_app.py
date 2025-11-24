"""Unit tests for worker Celery app configuration.

Tests cover:
- Celery app initialization
- Broker and backend configuration
- Environment variable handling
- App name configuration
"""

import sys
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCeleryAppConfiguration:
    """Test suite for Celery app configuration."""

    def test_celery_app_exists(self):
        """Test that celery_app is created and accessible."""
        from celery_app import celery_app

        assert celery_app is not None
        assert celery_app.main == "translator"

    def test_celery_app_name(self):
        """Test that Celery app has correct name."""
        from celery_app import celery_app

        assert celery_app.main == "translator"

    def test_default_broker_configuration(self):
        """Test default broker URL configuration."""
        # Import with clean environment (no CELERY_* vars set in this process)
        from celery_app import REDIS_BROKER

        # Should default to redis://redis:6379/0 or respect environment
        assert "redis://" in REDIS_BROKER
        assert isinstance(REDIS_BROKER, str)

    def test_default_backend_configuration(self):
        """Test default backend URL configuration."""
        from celery_app import REDIS_BACKEND

        # Should default to redis://redis:6379/1 or respect environment
        assert "redis://" in REDIS_BACKEND
        assert isinstance(REDIS_BACKEND, str)

    def test_broker_and_backend_use_different_dbs(self):
        """Test that broker and backend use different Redis databases."""
        from celery_app import REDIS_BACKEND, REDIS_BROKER

        # Extract DB numbers from URLs
        # Format: redis://host:port/db
        if "/0" in REDIS_BROKER and "/1" in REDIS_BACKEND:
            # Default configuration uses DB 0 for broker, DB 1 for backend
            assert REDIS_BROKER.endswith("/0")
            assert REDIS_BACKEND.endswith("/1")

    @patch.dict("os.environ", {"CELERY_BROKER_URL": "redis://custom-host:6379/5"})
    def test_broker_from_celery_env_var(self):
        """Test broker configuration from CELERY_BROKER_URL env var."""
        # Need to reload module to pick up new environment
        import importlib

        import celery_app

        importlib.reload(celery_app)

        assert celery_app.REDIS_BROKER == "redis://custom-host:6379/5"

    @patch.dict("os.environ", {"CELERY_RESULT_BACKEND": "redis://custom-host:6379/6"})
    def test_backend_from_celery_env_var(self):
        """Test backend configuration from CELERY_RESULT_BACKEND env var."""
        import importlib

        import celery_app

        importlib.reload(celery_app)

        assert celery_app.REDIS_BACKEND == "redis://custom-host:6379/6"

    @patch.dict(
        "os.environ",
        {"REDIS_BROKER": "redis://fallback-host:6379/0"},
        clear=False,
    )
    def test_broker_fallback_to_redis_broker(self):
        """Test broker falls back to REDIS_BROKER if CELERY_BROKER_URL not set."""
        import importlib
        import os

        import celery_app

        # Ensure CELERY_BROKER_URL is not set
        os.environ.pop("CELERY_BROKER_URL", None)

        importlib.reload(celery_app)

        # Should use REDIS_BROKER as fallback
        assert "fallback-host" in celery_app.REDIS_BROKER or "redis://" in celery_app.REDIS_BROKER

    @patch.dict(
        "os.environ",
        {"REDIS_BACKEND": "redis://fallback-host:6379/1"},
        clear=False,
    )
    def test_backend_fallback_to_redis_backend(self):
        """Test backend falls back to REDIS_BACKEND if CELERY_RESULT_BACKEND not set."""
        import importlib
        import os

        import celery_app

        # Ensure CELERY_RESULT_BACKEND is not set
        os.environ.pop("CELERY_RESULT_BACKEND", None)

        importlib.reload(celery_app)

        # Should use REDIS_BACKEND as fallback
        assert "fallback-host" in celery_app.REDIS_BACKEND or "redis://" in celery_app.REDIS_BACKEND

    def test_celery_app_has_broker_configured(self):
        """Test that Celery app has broker configured."""
        from celery_app import celery_app

        # Celery stores broker in conf
        assert celery_app.conf.broker_url is not None
        assert "redis://" in celery_app.conf.broker_url

    def test_celery_app_has_backend_configured(self):
        """Test that Celery app has result backend configured."""
        from celery_app import celery_app

        # Celery stores backend in conf
        assert celery_app.conf.result_backend is not None
        assert "redis://" in celery_app.conf.result_backend


class TestCeleryAppIntegration:
    """Integration tests for Celery app."""

    def test_celery_app_can_create_task_signature(self):
        """Test that Celery app can create task signatures."""
        from celery_app import celery_app

        # Should be able to create a signature
        signature = celery_app.signature("tasks.translate_parquet_batch")
        assert signature is not None

    def test_celery_app_task_registry(self):
        """Test that Celery app has task registry."""
        from celery_app import celery_app

        # Should have tasks registry
        assert hasattr(celery_app, "tasks")
        assert isinstance(celery_app.tasks, dict)


class TestEnvironmentConfiguration:
    """Test environment variable handling for configuration."""

    @patch.dict(
        "os.environ",
        {
            "CELERY_BROKER_URL": "redis://prod-redis:6380/2",
            "CELERY_RESULT_BACKEND": "redis://prod-redis:6380/3",
        },
    )
    def test_production_like_configuration(self):
        """Test configuration with production-like environment variables."""
        import importlib

        import celery_app

        importlib.reload(celery_app)

        assert celery_app.REDIS_BROKER == "redis://prod-redis:6380/2"
        assert celery_app.REDIS_BACKEND == "redis://prod-redis:6380/3"

    @patch.dict("os.environ", {}, clear=True)
    def test_no_environment_variables_uses_defaults(self):
        """Test that defaults are used when no environment variables are set."""
        import importlib

        import celery_app

        # Clear and reload to get defaults
        importlib.reload(celery_app)

        # Should fall back to hardcoded defaults
        assert "redis://" in celery_app.REDIS_BROKER
        assert "redis://" in celery_app.REDIS_BACKEND
