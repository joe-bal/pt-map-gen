"""Map generation utilities."""

from __future__ import annotations

from pathlib import Path
import os
import zipfile
from typing import Optional

import folium
import pandas as pd


class MapGenerator:
    """Generate Leaflet maps from GTFS feeds."""

    def __init__(self, gtfs_path: str | os.PathLike, osm_path: Optional[str | os.PathLike] = None) -> None:
        self.gtfs_path = Path(gtfs_path)
        self.osm_path = Path(osm_path) if osm_path else None

    def _load_stops(self) -> pd.DataFrame:
        """Load stops.txt from the GTFS feed."""
        if self.gtfs_path.is_dir():
            file_path = self.gtfs_path / "stops.txt"
            return pd.read_csv(file_path)
        with zipfile.ZipFile(self.gtfs_path) as zf:
            with zf.open("stops.txt") as f:
                return pd.read_csv(f)

    def generate(self, output_file: str = "map.html") -> Path:
        """Generate an HTML map with stop markers."""
        df = self._load_stops()
        if df.empty:
            raise ValueError("No stops found in GTFS feed")
        lat = df["stop_lat"].mean()
        lon = df["stop_lon"].mean()
        m = folium.Map(location=[lat, lon], zoom_start=11)
        for _, row in df.iterrows():
            folium.CircleMarker(
                location=[row["stop_lat"], row["stop_lon"]],
                radius=3,
                color="blue",
                fill=True,
                fill_color="blue",
                weight=1,
            ).add_to(m)
        out_path = Path(output_file)
        m.save(out_path)
        return out_path
