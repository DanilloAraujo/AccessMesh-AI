from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

class KeyVaultService:
    """
    Service class for interacting with Azure Key Vault secrets.

    This class provides methods to securely retrieve and store secrets in an Azure Key Vault instance.
    It handles authentication using Azure's DefaultAzureCredential and manages the SecretClient lifecycle.

    Attributes:
        _vault_url (str): The URL of the Azure Key Vault.
        _client (Optional[SecretClient]): The Azure Key Vault SecretClient instance.
        _enabled (bool): Indicates if the service is enabled and properly initialized.

    Methods:
        is_enabled: Returns True if the service is enabled and the client is initialized.
        get_secret: Retrieves a secret value by name, with an optional default.
        set_secret: Stores a secret value by name.
    """
    def __init__(self, vault_url: str) -> None:
        """
        Initialize the KeyVaultService with the given Azure Key Vault URL.

        Args:
            vault_url (str): The URL of the Azure Key Vault instance.
        """
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
        """
        Indicates whether the service is enabled and the client is initialized.

        Returns:
            bool: True if the service is enabled and client is available, False otherwise.
        """
        return self._enabled and self._client is not None

    def get_secret(self, name: str, default: str = "") -> str:
        """
        Retrieve a secret value by name from Azure Key Vault.

        Args:
            name (str): The name of the secret to retrieve.
            default (str, optional): The value to return if the secret is not found or service is disabled. Defaults to "".

        Returns:
            str: The secret value if found, otherwise the default value.
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
            logger.warning(
                "KeyVaultService: could not retrieve secret '%s' from %s — %s",
                name,
                self._vault_url,
                exc,
            )
            return default

    def set_secret(self, name: str, value: str) -> bool:
        """
        Store a secret value by name in Azure Key Vault.

        Args:
            name (str): The name of the secret to store.
            value (str): The value of the secret to store.

        Returns:
            bool: True if the secret was successfully stored, False otherwise.
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
    Get a cached instance of KeyVaultService for the given vault URL.

    Args:
        vault_url (str): The URL of the Azure Key Vault instance.

    Returns:
        KeyVaultService: The cached KeyVaultService instance for the given URL.
    """
    return KeyVaultService(vault_url)
