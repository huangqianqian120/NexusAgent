"""API error types for Nexus."""

from __future__ import annotations


class NexusApiError(RuntimeError):
    """Base class for upstream API failures."""


class AuthenticationFailure(NexusApiError):
    """Raised when the upstream service rejects the provided credentials."""


class RateLimitFailure(NexusApiError):
    """Raised when the upstream service rejects the request due to rate limits."""


class RequestFailure(NexusApiError):
    """Raised for generic request or transport failures."""
