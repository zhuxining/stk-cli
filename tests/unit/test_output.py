"""Tests for JSON envelope rendering."""

import json

from pydantic import BaseModel

from stk import output


class SampleData(BaseModel):
    value: int
    missing: str | None = None


def test_render_omits_unused_success_fields(capsys):
    output.render(SampleData(value=1))

    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is True
    assert payload["data"] == {"value": 1}
    assert "error" not in payload
    assert "generated_at" in payload["meta"]


def test_render_error_omits_data_and_uses_stable_shape(capsys):
    output.render_error("source_error", "boom")

    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is False
    assert payload["error"] == {"code": "source_error", "message": "boom"}
    assert "data" not in payload
    assert "generated_at" in payload["meta"]
