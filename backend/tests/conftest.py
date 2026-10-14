"""Generate the fake sample invoices before any test runs (idempotent)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from generate_samples import main  # noqa: E402

main()
