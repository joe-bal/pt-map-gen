# Transit Network Diagram Generator — Design Document

**Version:** 1.2\
**Date:** 29 June 2025\
**Author:** [Your Name]\
**Purpose:** Generate a vector-based, rail-style, stylized transit map for the state of Victoria using GTFS and OpenStreetMap (OSM) data. The system will support the display of all transit modes, including buses, trams, ferries, and trains, in a consistent diagrammatic style suitable for overlay on Leaflet maps. Visual line separation (parallel lines) will be handled dynamically at render time in the browser.

---

## 1. Objective

This project aims to develop an automated system producing high-quality, rail-style transit map data for Victoria, Australia, using publicly available GTFS and OSM data. The map will:

- Display transit routes (rail, bus, tram, ferry) with dynamically applied parallel lines.
- Maintain geographically accurate route centerlines without permanent geometry offset.
- Provide route ordering metadata for dynamic visual separation in Leaflet.
- Output vector data suitable for efficient browser-based rendering.
- Exclude stop placement and rendering logic (handled separately).

---

## 2. Scope

### Included:

- Map generation for Victoria, Australia.
- Support for bus, tram, ferry, rail (metro, commuter, regional).
- Geometry generation and shared corridor detection.
- Clean vector outputs (GeoJSON during development, vector tiles for production).
- Defined milestones with client demonstrations.

### Excluded:

- Global scale coverage.
- Stop rendering or placement logic.
- Detailed basemap styling (handled by Leaflet).

---

## 3. Data Inputs

### GTFS Data

- `stops.txt`: stop locations (for shape generation).
- `routes.txt`: route metadata.
- `trips.txt`: trip-to-route mapping.
- `stop_times.txt`: stop sequences.
- `shapes.txt`: optional route geometries.

### OpenStreetMap (OSM) Data

- Complete Victoria extract (road, rail, tram, ferry networks).

---

## 4. System Architecture

```
[GTFS Ingest] ──┐
                 │        ┌────────────────┐
[OSM Matching] ──┴───► [Shape Generation] ──► [Shared Corridor Detection] ──► [Parallel Line Ordering Metadata]
                                                │
[POI Data (Optional)] ────────────────────────► [Vector Data Export (GeoJSON)] ──► [Vector Tile Generation]
```

*Note: Parallel line visual offsets are handled dynamically in Leaflet.*

---

## 5. Detailed Pipeline Design

### 5.1 GTFS Ingest

- Parse and validate GTFS data.
- Link trips to routes and stops.
- Identify missing or low-quality shapes.
- Snap all adequate-quality shapes to the OSM road/rail network.

### 5.2 Shape Generation via OSM Matching

- For missing shapes:
  - Extract stop sequences.
  - Perform pathfinding along OSM networks.
  - Generate realistic, geographically aligned route geometry.

### 5.3 Shared Corridor Detection

- Rasterize route geometries onto a sparse raster (resolution: 1 pixel/meter).
- Extract shared corridor centerlines using skeletonization.
- Build topology indicating shared and diverging segments.

### 5.4 Parallel Line Ordering Metadata

- Identify participating routes per corridor.
- Apply Integer Linear Programming (ILP) to determine optimal line ordering.
- **Metadata format:** Assign integer ordering indices (1, 2, 3…) for relative route positions.
- Leaflet applies visual offsets dynamically using these indices.

### 5.5 Vector Data Export

- **Development:** GeoJSON files with geometries and ordering metadata.
- **Production:** Vector tiles optimized for efficient rendering.

---

## 6. Output Formats

- **Development:** GeoJSON
- **Production:** Mapbox Vector Tile (MVT)

*Front-end responsibilities:* Leaflet dynamically applies visual offsets based on provided metadata, zoom level, and user interactions.

---

## 7. Technical Considerations

| Component            | Recommended Tools/Technologies            |
| -------------------- | ----------------------------------------- |
| GTFS Parsing         | Python, Pandas                            |
| OSM Matching         | OSRM, Valhalla                            |
| Skeletonization      | OpenCV, custom sparse raster processing   |
| ILP Optimization     | Google OR-Tools, PuLP                     |
| Geometric Processing | Shapely, PostGIS                          |
| Vector Tile Output   | Tippecanoe, Mapbox tools, custom pipeline |

---

## 8. Milestones & Client Demonstrations

| Milestone                          | Demonstration Contents                      | Estimated Timeline |
| ---------------------------------- | ------------------------------------------- | ------------------ |
| Data Ingest & Shape Generation     | Basic route shapes (GeoJSON)                | Week 3             |
| Shared Corridor Detection          | Identified shared corridors                 | Week 5             |
| Parallel Line Ordering Metadata    | Dynamic parallel rendering proof-of-concept | Week 7             |
| Complete Victoria Coverage GeoJSON | Full GeoJSON dataset                        | Week 10            |
| Vector Tile Production             | Final vector tile output                    | Week 12            |

---

## 9. Future Enhancements (Post-MVP)

- Stop rendering as separate module.
- Per-mode visibility toggles.
- Dynamic POI labeling.
- Global expansion.

---

## 10. Conclusion

This document outlines the development of a scalable, automated transit map generation pipeline for Victoria, Australia, delivering dynamic, rail-style visual representations through Leaflet integration. All visual offsets are handled dynamically, ensuring geographic accuracy and providing flexibility in rendering.

