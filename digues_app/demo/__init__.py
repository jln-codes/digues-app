"""Dataset synthetique de demonstration pour la webapp SIRS."""

from .seed import (
    DEMO_SEED,
    DemoSeedError,
    DemoSeedReport,
    reset_demo_dataset,
    seed_demo_cursor,
    seed_demo_dataset,
)

__all__ = [
    "DEMO_SEED",
    "DemoSeedError",
    "DemoSeedReport",
    "reset_demo_dataset",
    "seed_demo_cursor",
    "seed_demo_dataset",
]
