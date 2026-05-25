"""Tests for JSON envelope rendering."""

import json

from pydantic import BaseModel

from stk import output


class SampleData(BaseModel):
    value: int
    missing: str | None = None


def test_render_can_omit_none_from_data(capsys):
    output.render(SampleData(value=1), exclude_none=True)

    payload = json.loads(capsys.readouterr().out)

    assert payload["data"] == {"value": 1}
    assert payload["error"] is None
