import argparse

from backend.app.config import settings
from backend.app.ingest import ingest_version


def main() -> None:
    """Run the documentation ingestion pipeline from the command line."""
    parser = argparse.ArgumentParser(description="Ingest local Java documentation into a vector index.")
    parser.add_argument("--version", default=settings.default_version, help="Documentation version folder, e.g. jdk8")
    args = parser.parse_args()

    summary = ingest_version(settings, args.version, progress=lambda message: print(message, flush=True))
    print(
        f"Ingested {summary['documents']} documents into {summary['chunks']} chunks "
        f"for {summary['version']} at {summary['indexPath']}"
    )


if __name__ == "__main__":
    main()
