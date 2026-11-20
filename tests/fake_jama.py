"""An invented Jama project, served over mocked HTTP."""

from __future__ import annotations

import copy
from typing import Any

import httpx
import respx

from .conftest import envelope

PROJECT = {"id": 12, "fields": {"name": "Widget Assembly", "projectKey": "WA"}}

ITEM_TYPES: dict[int, dict[str, Any]] = {
    34: {
        "id": 34,
        "typeKey": "REQ",
        "display": "Requirement",
        "fields": [
            {"name": "name", "label": "Name", "fieldType": "STRING"},
            {"name": "description", "label": "Description", "fieldType": "TEXT"},
        ],
    },
    35: {
        "id": 35,
        "typeKey": "TC",
        "display": "Test Case",
        "category": "TEST_CASE",
        "fields": [
            {"name": "name", "label": "Name", "fieldType": "STRING"},
            {"name": "testCaseSteps", "label": "Steps", "fieldType": "STEPS"},
        ],
    },
    36: {"id": 36, "typeKey": "FLD", "display": "Folder", "fields": []},
}


def jama_item(item_id: int, name: str, description: str, *, item_type: int = 34) -> dict[str, Any]:
    """An item as Jama sends it."""
    key = {34: "REQ", 35: "TC"}.get(item_type, "FLD")
    return {
        "id": item_id,
        "documentKey": f"WA-{key}-{item_id}",
        "globalId": f"GID-{item_id}",
        "itemType": item_type,
        "version": 1,
        "lastActivityDate": "2026-10-01T14:03:12.000+0000",
        "fields": {"name": name, "description": description},
        "location": {"parent": {"project": 12}},
    }


class FakeJama:
    """The project's items, editable between reads."""

    def __init__(self) -> None:
        self.items: dict[int, dict[str, Any]] = {
            101: jama_item(101, "Brake temperature", "<p>Stays below 450&deg;C during a hot stop.</p>"),
            102: jama_item(102, "Pedal force", "<p>Under 500 N at full braking.</p>"),
            201: jama_item(201, "Hot stop test", "<p>Steps.</p>", item_type=35),
        }
        self.truncate_type: int | None = None

    def set_field(self, item_id: int, name: str, value: Any) -> None:
        self.items[item_id] = copy.deepcopy(self.items[item_id])
        self.items[item_id]["fields"][name] = value
        self.items[item_id]["version"] += 1

    def add(self, item_id: int, name: str, description: str) -> None:
        self.items[item_id] = jama_item(item_id, name, description)

    def install(self, router: respx.MockRouter) -> None:
        router.get("/projects/12").respond(json={"data": PROJECT})
        router.get("/projects/12/itemtypes").respond(
            json=envelope([{k: v for k, v in t.items() if k != "fields"} for t in ITEM_TYPES.values()])
        )
        for type_id, item_type in ITEM_TYPES.items():
            router.get(f"/itemtypes/{type_id}").respond(json={"data": item_type})
        router.get("/abstractitems").mock(side_effect=self._abstract_items)

    def _abstract_items(self, request: httpx.Request) -> httpx.Response:
        item_type = int(request.url.params["itemType"])
        rows = [i for i in self.items.values() if i["itemType"] == item_type]
        if request.url.params.get("maxResults") == "1":
            return httpx.Response(200, json=envelope(rows[:1], total=len(rows)))
        if item_type == self.truncate_type:
            return httpx.Response(200, json=envelope(rows[:1], total=len(rows), result_count=1))
        return httpx.Response(200, json=envelope(rows, total=len(rows)))
