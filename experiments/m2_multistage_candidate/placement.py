"""V3 M2 placement functions used by the controlled structural study."""

from rcaps.v3.placement import (HERE as V3_HERE, ROOT, digest, from_single_boundary,
                                measure, normalize, objective, save, signature,
                                validate)

from pathlib import Path


HERE = Path(__file__).resolve().parent
