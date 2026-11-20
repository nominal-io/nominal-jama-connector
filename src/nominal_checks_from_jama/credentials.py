"""Keeping the Jama secret in the operating system's credential manager, out of the config file.

The ``keyring`` library reaches the credential manager on each operating system.
"""

from __future__ import annotations

import keyring
import keyring.errors

from nominal_checks_from_jama._jama import ClientCredentials, JamaClient
from nominal_checks_from_jama.config import AuthKind, JamaSettings


class CredentialsError(Exception):
    """The Jama secret isn't available."""


class MissingSecretError(CredentialsError):
    """The credential manager has no secret for this Jama instance and account. The ``login`` command stores one."""


def keyring_service(settings: JamaSettings) -> str:
    """The name the credential manager stores the secret under: one per Jama instance.

    Args:
        settings (JamaSettings): The Jama settings.

    Returns:
        str: The service name.
    """
    return f"nominal-checks-from-jama:{settings.base_url.rstrip('/')}"


def save_secret(settings: JamaSettings, secret: str) -> None:
    """Store the client secret, password or token in the operating system's credential manager.

    Args:
        settings (JamaSettings): The Jama settings; the secret is stored under their account.
        secret (str): The secret.

    Raises:
        CredentialsError: When there's no account to store it under, or no credential manager.
    """
    if not settings.account:
        raise CredentialsError("[jama] account is empty, so there's nothing to store the secret under.")
    try:
        keyring.set_password(keyring_service(settings), settings.account, secret)
    except keyring.errors.KeyringError as error:
        raise CredentialsError(
            f"Couldn't store the secret in your operating system's credential manager: {error}"
        ) from None


def load_secret(settings: JamaSettings) -> str:
    """Read the secret from the operating system's credential manager.

    Args:
        settings (JamaSettings): The Jama settings.

    Returns:
        str: The secret.

    Raises:
        MissingSecretError: When the credential manager has no secret for this instance and account.
        CredentialsError: When the credential manager can't be read.
    """
    try:
        secret = keyring.get_password(keyring_service(settings), settings.account)
    except keyring.errors.KeyringError as error:
        raise CredentialsError(f"Couldn't read your operating system's credential manager: {error}") from None
    if not secret:
        raise MissingSecretError(
            f"No secret for {settings.account!r} at {settings.base_url} in your operating system's credential manager."
        )
    return secret


def jama_client(settings: JamaSettings, secret: str | None = None) -> JamaClient:
    """A Jama client signed in as the settings say.

    Args:
        settings (JamaSettings): The Jama settings.
        secret (str | None): The secret; read from the operating system's credential manager when None.

    Returns:
        JamaClient: The client.
    """
    secret = secret if secret is not None else load_secret(settings)
    if settings.auth is AuthKind.BASIC:
        return JamaClient.from_basic(settings.base_url, settings.account, secret)
    if settings.auth is AuthKind.TOKEN:
        return JamaClient.from_token(settings.base_url, secret)
    return JamaClient(settings.base_url, ClientCredentials(settings.account, secret))
