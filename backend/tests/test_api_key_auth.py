"""Tests for API key generation and validation."""

import hashlib

from app.core.api_key_auth import API_KEY_PREFIX, generate_api_key


class TestGenerateApiKey:
    """Tests for API key generation."""

    def test_generates_key_with_prefix(self) -> None:
        """Generated key starts with the expected prefix."""
        raw_key, key_hash, key_prefix = generate_api_key()
        assert raw_key.startswith(API_KEY_PREFIX)

    def test_key_hash_matches(self) -> None:
        """Hash of raw key matches the returned hash."""
        raw_key, key_hash, key_prefix = generate_api_key()
        expected_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        assert key_hash == expected_hash

    def test_key_prefix_matches(self) -> None:
        """Key prefix matches the first 8 chars of raw key."""
        raw_key, key_hash, key_prefix = generate_api_key()
        assert key_prefix == raw_key[:8]

    def test_keys_are_unique(self) -> None:
        """Two generated keys should be different."""
        key1, _, _ = generate_api_key()
        key2, _, _ = generate_api_key()
        assert key1 != key2

    def test_key_length(self) -> None:
        """Raw key should have expected length (prefix + 40 hex chars)."""
        raw_key, _, _ = generate_api_key()
        assert len(raw_key) == len(API_KEY_PREFIX) + 40

    def test_hash_length(self) -> None:
        """Hash should be 64 chars (SHA-256 hex)."""
        _, key_hash, _ = generate_api_key()
        assert len(key_hash) == 64
