# pt-map-gen

`ptmapgen` is a small tool for creating interactive public transport maps from
GTFS data. The generated output is a simple HTML file rendered with Leaflet.

This project aims to automate map creation for Victoria, Australia, but the
code can be used with any valid GTFS feed.

## Quick start

Install the package in a virtual environment:

```bash
pip install -e .
```

Generate a map from a GTFS zip file:

```bash
ptmapgen path/to/gtfs.zip output.html
```

The current implementation only plots stop locations. Additional features will
be added over time.

## Project structure

- `ptmapgen/` – library package
- `ptmapgen/cli.py` – command line entry point
- `ptmapgen/generator.py` – map generation logic
