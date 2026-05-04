import re
import shutil
from pathlib import Path
from uuid import uuid4

import pytest


@pytest.fixture
def tmp_path(request):
    """Provide per-test temporary directories with sandbox-friendly cleanup."""
    base_dir = Path.cwd() / "test_tmp"
    base_dir.mkdir(exist_ok=True)

    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", request.node.nodeid)
    path = base_dir / f"{safe_name}_{uuid4().hex}"
    path.mkdir()

    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
        try:
            base_dir.rmdir()
        except OSError:
            pass
