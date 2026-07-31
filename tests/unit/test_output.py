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
    assert payload["status"] == "success"
    assert payload["data"] == {"value": 1}
    assert "error" not in payload
    assert "generated_at" in payload["meta"]


def test_render_error_omits_data_and_uses_stable_shape(capsys):
    output.render_error("source_error", "boom")

    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is False
    assert payload["status"] == "failed"
    assert payload["error"] == {"code": "source_error", "message": "boom"}
    assert "data" not in payload
    assert "generated_at" in payload["meta"]


class PartialData(BaseModel):
    failures: list[dict[str, str]]


def test_render_marks_item_failures_as_partial(capsys):
    output.render(
        PartialData(
            failures=[
                {
                    "symbol": "688825.SH",
                    "code": "indicator_error",
                    "message": "insufficient history",
                }
            ]
        )
    )

    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is True
    assert payload["status"] == "partial"
    assert payload["data"]["failures"][0]["symbol"] == "688825.SH"
