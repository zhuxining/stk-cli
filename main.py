"""Entry point for stk-cli."""

from app import output
from app.cli import app
from app.errors import StkError


def main() -> None:
    try:
        app()
    except StkError as e:
        output.render_error(type(e).__name__, e.message)
    except Exception as e:
        output.render_error("UnexpectedError", str(e))


if __name__ == "__main__":
    main()
