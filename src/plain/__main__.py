"""CLI entrypoint for Plain."""

from .app import create_app


def main() -> None:
    """Run the Textual app."""
    app = create_app()
    app.run()


if __name__ == "__main__":
    main()

