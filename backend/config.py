"""Central limits and workspace settings."""
from pathlib import Path
import os

HOME = Path(os.environ.get("HEXROT_HOME", str(Path.home() / ".hexrot"))).expanduser().resolve()
MAX_FILE_SIZE = 32 * 1024 * 1024
MAX_MUTATIONS = 50
MAX_METADATA_VALUE = 64 * 1024
MAX_LOG = 64 * 1024
