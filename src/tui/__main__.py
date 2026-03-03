"""CLI entry point -- starts FastAPI server for Rust TUI."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Jikai API Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    import uvicorn

    uvicorn.run("src.api.main:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
