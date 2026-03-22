"""Azure Key Vault secrets provider."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)


class KeyVaultService:
    """Thread-safe, lazily-authenticated Azure Key Vault client."""

    def __init__(self, vault_url: str) -> None:
        self._vault_url = vault_url.rstrip("/")
        self._client = None
        self._enabled = False

        if not vault_url:
            logger.debug("KeyVaultService: no vault URL provided — service disabled.")
            return

        try:
            from azure.identity import DefaultAzureCredential  # type: ignore[import]
            from azure.keyvault.secrets import SecretClient  # type: ignore[import]

            credential = DefaultAzureCredential(
                # Exclude interactive browser to avoid blocking startup in CI/CD.
                exclude_interactive_browser_credential=True,
            )
            self._client = SecretClient(
                vault_url=self._vault_url,
                credential=credential,
            )
            self._enabled = True
            logger.info("KeyVaultService: initialised — vault=%s", self._vault_url)
        except ImportError as exc:
            logger.error(
                "KeyVaultService: azure-keyvault-secrets or azure-identity not installed — %s", exc
            )
        except Exception as exc:
            logger.error("KeyVaultService: failed to initialise client — %s", exc)

    @property
    def is_enabled(self) -> bool:
        """True when the client was initialised successfully."""
        return self._enabled and self._client is not None

    def get_secret(self, name: str, default: str = "") -> str:
        """
        Retrieve the latest version of *name* from Key Vault.

        Returns *default* when:
          - The service is not enabled (missing vault URL / credentials).
          - The secret does not exist in the vault.
          - The vault is unreachable (network timeout, permission denied, etc.).

        This non-throwing contract means application startup is never blocked
        by a missing optional secret — the validator in Settings will emit the
        appropriate warning instead.
        """
        if not self.is_enabled or self._client is None:
            return default
        try:
            result = self._client.get_secret(name)
            value = result.value
            if value is None:
                return default
            logger.debug("KeyVaultService: retrieved '%s' (len=%d)", name, len(value))
            return value
        except Exception as exc:
            # Log at WARNING so misconfigurations are visible without crashing.
            logger.warning(
                "KeyVaultService: could not retrieve secret '%s' from %s — %s",
                name,
                self._vault_url,
                exc,
            )
            return default

    def set_secret(self, name: str, value: str) -> bool:
        """
        Create or update *name* in Key Vault.

        Returns True on success, False on failure.
        Requires the caller's identity to have the *Key Vault Secrets Officer* role.
        """
        if not self.is_enabled or self._client is None:
            logger.warning("KeyVaultService: set_secret called but service is disabled.")
            return False
        try:
            self._client.set_secret(name, value)
            logger.info("KeyVaultService: secret '%s' written to %s", name, self._vault_url)
            return True
        except Exception as exc:
            logger.error(
                "KeyVaultService: failed to write secret '%s' — %s", name, exc
            )
            return False


@lru_cache(maxsize=8)
def get_keyvault_service(vault_url: str) -> KeyVaultService:
    """
    Return a cached KeyVaultService instance for *vault_url*.

    The ``lru_cache`` ensures a single client per process lifetime, which is
    important because DefaultAzureCredential performs token acquisition (and
    caches the token internally) — creating multiple instances would waste
    network calls and memory.
    """
    return KeyVaultService(vault_url)
