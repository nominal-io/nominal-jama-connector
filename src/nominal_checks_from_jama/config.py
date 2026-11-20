"""The settings, kept in a TOML file (``jama-checks.toml`` by default)."""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

import tomli_w

from nominal_checks_from_jama._jama import instance_url
from nominal_checks_from_jama.kinds import ItemKind
from nominal_checks_from_jama.markers import PAIRS

DEFAULT_CONFIG = "jama-checks.toml"

PRIORITIES = ("P0", "P1", "P2", "P3", "P4")
"""Nominal check priorities, from most to least severe."""

CHANNEL_MARKERS = tuple(PAIRS)
"""Pairs that can mark a channel name in a requirement, besides backticks, which are always on."""


class AuthKind(StrEnum):
    """How the tool signs in to Jama."""

    CLIENT_CREDENTIALS = "client_credentials"
    """An API client ID and secret."""
    BASIC = "basic"
    """A username and password. Doesn't work on instances that use single sign-on."""
    TOKEN = "token"
    """An access token, which nothing renews."""


@dataclass(frozen=True)
class JamaSettings:
    """The Jama project to read and how to sign in. The secret is kept in the operating system's credential manager.

    Attributes:
        base_url (str): The Jama instance's URL. The URL of any page on it, copied from the
            browser, works too: it's cut to the instance's URL.
        project (str): The project id.
        item_types (tuple[str, ...]): The item type ids whose items are requirements.
        test_case_types (tuple[str, ...]): The item type ids whose items are test cases.
        auth (AuthKind): How to sign in.
        account (str): The API client ID for ``client_credentials``, the username for ``basic``,
            and a name of your choice for ``token``. The credential manager stores the secret under it.

    Raises:
        ValueError: When ``base_url`` isn't an http or https URL.
    """

    base_url: str
    project: str
    item_types: tuple[str, ...] = ()
    auth: AuthKind = AuthKind.CLIENT_CREDENTIALS
    account: str = ""
    test_case_types: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # one form of the URL, so lineages and the stored secret's name don't depend on how it was pasted
        object.__setattr__(self, "base_url", instance_url(self.base_url))

    def types(self, kind: ItemKind) -> tuple[str, ...]:
        """The item type ids to read for a kind of item.

        Args:
            kind (ItemKind): Requirements or test cases.

        Returns:
            tuple[str, ...]: ``item_types`` or ``test_case_types``.
        """
        return self.item_types if kind is ItemKind.REQUIREMENTS else self.test_case_types


@dataclass(frozen=True)
class NominalSettings:
    """Where the checklist goes and what its checks look like.

    Attributes:
        profile (str): The Nominal config profile to connect with.
        checklist_name (str): The requirements checklist's name when it's created; ``<project name>
            requirements`` when empty. Renaming it in Nominal afterwards is fine.
        priority (str): The priority of new checks, ``P0`` to ``P4``.
        ref_name (str): The data source that channels marked in requirements are read from.
        channel_markers (tuple[str, ...]): Pairs that mark a channel name besides backticks, from
            ``{}``, ``[]`` and ``<>``.
        test_case_checklist_name (str): The test case checklist's name when it's created;
            ``<project name> test cases`` when empty.
    """

    profile: str = "default"
    checklist_name: str = ""
    priority: str = "P3"
    ref_name: str = "default"
    channel_markers: tuple[str, ...] = ()
    test_case_checklist_name: str = ""

    def checklist_name_for(self, kind: ItemKind) -> str:
        """The name set for a kind's checklist, or ``""`` for the default.

        Args:
            kind (ItemKind): Requirements or test cases.

        Returns:
            str: ``checklist_name`` or ``test_case_checklist_name``.
        """
        return self.checklist_name if kind is ItemKind.REQUIREMENTS else self.test_case_checklist_name


@dataclass(frozen=True)
class Config:
    """Everything in ``jama-checks.toml``.

    Attributes:
        jama (JamaSettings): The Jama project and sign-in.
        nominal (NominalSettings): The checklist.
        path (Path | None): The file it was read from.
    """

    jama: JamaSettings
    nominal: NominalSettings = field(default_factory=NominalSettings)
    path: Path | None = None

    @classmethod
    def load(cls, path: str | Path = DEFAULT_CONFIG) -> Config:
        """Read the settings from a TOML file.

        Args:
            path (str | Path): The file.

        Returns:
            Config: The settings.

        Raises:
            FileNotFoundError: When the file doesn't exist. ``nominal-checks-from-jama init`` creates it.
            ValueError: When a required setting is missing or a value is invalid.
        """
        file = Path(path)
        with file.open("rb") as handle:
            data = tomllib.load(handle)
        return cls.from_dict(data, path=file)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: Path | None = None) -> Config:
        """Build the settings from the TOML file's contents.

        Args:
            data (Mapping[str, Any]): The parsed TOML.
            path (Path | None): The file it came from.

        Returns:
            Config: The settings.

        Raises:
            ValueError: When a required setting is missing or a value is invalid.
        """
        jama = _table(data, "jama")
        nominal = _table(data, "nominal")
        base_url = str(jama.get("base_url", "")).strip()
        project = _id(jama.get("project"))
        if not base_url or not project:
            raise ValueError("[jama] needs base_url and project.")
        try:
            auth = AuthKind(str(jama.get("auth", AuthKind.CLIENT_CREDENTIALS)))
        except ValueError:
            raise ValueError(f"[jama] auth must be one of {', '.join(AuthKind)}.") from None
        defaults = NominalSettings()
        priority = str(nominal.get("priority", defaults.priority)).strip().upper()
        if priority not in PRIORITIES:
            raise ValueError(f"[nominal] priority must be one of {', '.join(PRIORITIES)}.")
        ref_name = str(nominal.get("ref_name", defaults.ref_name)).strip()
        if not ref_name:
            raise ValueError("[nominal] ref_name can't be empty.")
        markers = nominal.get("channel_markers", ())
        if not isinstance(markers, list | tuple) or any(m not in CHANNEL_MARKERS for m in markers):
            raise ValueError(f"[nominal] channel_markers must be a list drawn from {', '.join(CHANNEL_MARKERS)}.")
        return cls(
            jama=JamaSettings(
                base_url=base_url,
                project=project,
                item_types=_ids(jama.get("item_types", ()), "item_types"),
                auth=auth,
                account=str(jama.get("account", "")),
                test_case_types=_ids(jama.get("test_case_types", ()), "test_case_types"),
            ),
            nominal=NominalSettings(
                profile=str(nominal.get("profile", defaults.profile)),
                checklist_name=str(nominal.get("checklist_name", "")).strip(),
                priority=priority,
                ref_name=ref_name,
                channel_markers=tuple(dict.fromkeys(markers)),
                test_case_checklist_name=str(nominal.get("test_case_checklist_name", "")).strip(),
            ),
            path=path,
        )

    def to_dict(self) -> dict[str, Any]:
        """The settings as the TOML file holds them.

        Returns:
            dict[str, Any]: The TOML tables.
        """
        nominal: dict[str, Any] = {"profile": self.nominal.profile}
        if self.nominal.checklist_name:
            nominal["checklist_name"] = self.nominal.checklist_name
        if self.nominal.test_case_checklist_name:
            nominal["test_case_checklist_name"] = self.nominal.test_case_checklist_name
        nominal |= {
            "priority": self.nominal.priority,
            "ref_name": self.nominal.ref_name,
            "channel_markers": list(self.nominal.channel_markers),
        }
        return {
            "jama": {
                "base_url": self.jama.base_url,
                "project": self.jama.project,
                "item_types": list(self.jama.item_types),
                "test_case_types": list(self.jama.test_case_types),
                "auth": str(self.jama.auth),
                "account": self.jama.account,
            },
            "nominal": nominal,
        }

    def save(self, path: str | Path | None = None) -> Path:
        """Write the settings to a TOML file.

        Args:
            path (str | Path | None): The file; the one it was loaded from when None.

        Returns:
            Path: The file written.
        """
        target = Path(path) if path is not None else (self.path or Path(DEFAULT_CONFIG))
        target.write_text(tomli_w.dumps(self.to_dict()), encoding="utf-8")
        return target

    def with_path(self, path: Path) -> Config:
        """The same settings, read from ``path``.

        Args:
            path (Path): The config file.

        Returns:
            Config: The settings.
        """
        return replace(self, path=path)


def _table(data: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, Mapping):
        raise ValueError(f"[{name}] must be a table.")
    return value


def _id(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, int | str):
        return ""
    return str(value).strip()


def _ids(values: object, setting: str) -> tuple[str, ...]:
    if isinstance(values, str | int):
        values = [values]
    if not isinstance(values, Iterable):
        raise ValueError(f"[jama] {setting} must be a list of ids.")
    ids = tuple(_id(v) for v in values)
    if any(not i for i in ids):
        raise ValueError(f"[jama] {setting} must be a list of ids.")
    return ids
