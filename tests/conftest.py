"""Shared fixtures: isolated data dir + synthetic satellite scenes.

SATQUERY_DATA_DIR is set BEFORE any backend import so job/artifact stores
stay out of the developer's real data directory.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

_TMP_DATA = Path(tempfile.mkdtemp(prefix="satquery_test_data_"))
os.environ["SATQUERY_DATA_DIR"] = str(_TMP_DATA)

from backend.utils import synth  # noqa: E402
from backend.utils import assets as assets_reg  # noqa: E402


@pytest.fixture(scope="session")
def optical_pair(tmp_path_factory):
    """Bi-temporal optical pair + SAR pair with a known vegetation-loss patch."""
    out = tmp_path_factory.mktemp("scenes")
    return synth.write_pair(str(out))


@pytest.fixture(scope="session")
def registered_assets(optical_pair):
    """Register the synthetic scenes as assets (as if uploaded)."""
    from backend.geospatial import raster as graster
    ids = {}
    for key, path in optical_pair.items():
        sensor = "sar" if key.startswith("sar") else "optical"
        report = graster.validate_raster(path, sensor)
        assert report["valid"], report
        aid = f"asset_{key}"
        assets_reg.register_asset(aid, path, report,
                                  {"capture_date": "2025-06-01" if "before" in key
                                   else "2025-09-01", "sensor_type": sensor})
        ids[key] = aid
    return {"ids": ids, "paths": optical_pair}


@pytest.fixture()
def two_optical_assets(registered_assets):
    return [{"asset_id": registered_assets["ids"]["optical_before"],
             "capture_date": "2025-06-01", "sensor_type": "optical"},
            {"asset_id": registered_assets["ids"]["optical_after"],
             "capture_date": "2025-09-01", "sensor_type": "optical"}]
