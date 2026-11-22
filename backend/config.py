"""Central limits and workspace settings."""
from pathlib import Path
import os

HOME = Path(os.environ.get("HEXROT_HOME", str(Path.home() / ".hexrot"))).expanduser().resolve()
# NOTE: there is intentionally no MAX_FILE_SIZE cap. Uploads are streamed to
# disk and may be any size the local disk can hold. Per-request mutation
# output caps remain available via MutationRequest.max_file_size (optional).
MAX_MUTATIONS = 50
MAX_METADATA_VALUE = 64 * 1024
MAX_LOG = 64 * 1024
