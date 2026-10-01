"""Pytest bootstrap for the OrcaRouter integration tests.

The repository ships no test framework, so these tests are self-contained: they only need
``pytest`` plus the standard library for the pure ``core.orcarouter`` layer, and ``flask`` for the
transport tests.  Run them with::

    python -m pytest OntiCards_Api/test_orcarouter -v

from the repository root (or ``python -m pytest test_orcarouter -v`` from ``OntiCards_Api``).
"""

import os
import sys

API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)
