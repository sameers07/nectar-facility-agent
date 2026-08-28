class LLMProviderError(Exception):
    """The LLM API call itself failed (network, auth, rate limit, timeout)."""


class RoutingError(Exception):
    """The LLM responded but didn't return a valid, parseable routing contract."""
