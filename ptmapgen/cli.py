"""Command line interface for ptmapgen."""

from __future__ import annotations

import argparse

from .generator import MapGenerator


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate Leaflet maps from GTFS data")
    parser.add_argument("gtfs", help="Path to GTFS zip file or directory")
    parser.add_argument("output", help="Output HTML file", nargs="?", default="map.html")
    args = parser.parse_args(argv)

    gen = MapGenerator(args.gtfs)
    out_path = gen.generate(args.output)
    print(f"Map written to {out_path}")


if __name__ == "__main__":
    main()
