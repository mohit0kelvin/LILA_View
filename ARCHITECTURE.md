# Architecture

This document outlines the design decisions, data flow, and engineering tradeoffs behind the LILA BLACK Player Journey Visualizer.

## Technology Stack

The stack was selected to optimize for development velocity, deployment simplicity, and clarity of presentation — given the 10–15 hour scope of the assignment.

| Layer | Selection |
|---|---|
| Web framework | Streamlit |
| Visualization | Plotly |
| Hosting | Streamlit Community Cloud |
| Data format | Pre-computed Parquet files |

**Streamlit** enables rapid construction of interactive data apps in pure Python, eliminating the need for a separate frontend codebase. The entire application lives in a single `app.py` file with native widgets for filters, sliders, and tabs. While Streamlit offers less low-level control than React, the brief's emphasis on quality-over-quantity made it a strong fit.

**Plotly** provides interactive map rendering with built-in zoom, pan, hover tooltips, and legend toggling. It handles ~25,000 markers without performance tuning. Alternatives (matplotlib, deck.gl, D3) were either too static or disproportionate to the project's complexity.

**Streamlit Community Cloud** offers GitHub-integrated continuous deployment via push. It is free, zero-configuration, and ideal for the static-asset-heavy nature of the app.

**Pre-computed Parquet files** reduce the 1,243 raw files to three clean files (~594 KB total) during a one-time offline preprocessing step. This shifts the runtime cost of parquet parsing out of the user-facing application.

## Data Flow

The system follows a clear separation between offline data preparation and runtime serving.

```
Raw data (1,243 parquet files, ~89,000 rows)
        │
        ▼
prepare_data.py  (one-time, run locally)
   • Decode 'event' bytes column to UTF-8 strings
   • Add is_human flag via UUID regex on user_id
   • Add date column derived from folder structure
   • Compute ts_relative (per-match elapsed time)
   • Downsample position events 3x to reduce file size
   • Aggregate per-match summary statistics
        │
        ▼
data/processed/  (committed to repository)
   • events.parquet  — 16,045 combat and loot events
   • paths.parquet   — 24,769 downsampled position samples
   • matches.parquet — 796 match summaries
        │
        ▼
app.py  (loads files at startup, cached via @st.cache_data)
   • Sidebar filters: map, date, match, multi-player toggle, layer visibility
   • Markers View: per-player colored paths and event markers, with timeline playback
   • Heatmap View: aggregate kill, death, and traffic visualizations
        │
        ▼
Plotly figure rendered in the browser
```

This split offers two key benefits. First, runtime performance: the app loads three small files in milliseconds instead of parsing 1,243 raw files on every page load. Second, deployment simplicity: Streamlit Cloud serves the processed files as static assets, with no backend service required.

## Coordinate Mapping

The transformation from in-game world coordinates to minimap pixel coordinates is the most error-prone aspect of the visualization. It is implemented as a single, tested utility function in `utils.py`:

```python
def world_to_pixel(x, z, map_id, img_w, img_h):
    cfg = MAP_CONFIGS[map_id]
    u = (x - cfg["origin_x"]) / cfg["scale"]
    v = (z - cfg["origin_z"]) / cfg["scale"]
    return u * img_w, (1 - v) * img_h
```

Two implementation details required deliberate handling:

**Image dimensions vary by map and do not match the documented values.** The data README specifies all minimaps as 1024×1024 pixels. The actual files are 4320×4320 (AmbroseValley), 2160×2158 (GrandRift), and 9000×9000 (Lockdown). The transform reads each minimap's true dimensions at runtime via `PIL.Image.size` rather than relying on the documented values. This was caught early in development when an initial visualization rendered all events compressed into the upper-left quadrant of the AmbroseValley map.

**The `y` column represents elevation, not a 2D coordinate.** The data schema includes `x`, `y`, and `z` columns, but `y` is the vertical/elevation axis in the 3D world. The 2D minimap projection uses only `x` and `z`. The transform makes this explicit by accepting only those two coordinates.

The function is verified by a self-test (`python utils.py`) that validates the README's worked example along with origin and (origin + scale) corner cases for all three maps.

## Assumptions and Data Interpretations

Several aspects of the data required interpretation. Each is documented here so the reasoning is reviewable.

**Bot vs. human classification.** Per the data README, human players have UUID-shaped `user_id` values while bots have short numeric IDs. This classification is performed once during preprocessing using a UUID regex, and stored as a boolean `is_human` column. The application never re-classifies — it simply filters on the column.

**Single-file matches.** Of the 796 matches in the dataset, 743 contain telemetry from only a single participant. These are most plausibly lone-wolf sessions, internal tests, or disengaged players rather than full multi-player matches. They are retained in the dataset but isolated behind a "Multi-player matches only (5+ files)" sidebar toggle. This isolation revealed a notable correlation: all 39 storm deaths in the entire dataset occur in single-file matches (see INSIGHTS.md).

**Timestamp interpretation.** The data README describes the `ts` column as "milliseconds elapsed within the match, not wall-clock time." This interpretation is honored in the pipeline. Empirically, match durations under this interpretation are very short (most under one second of internal time), which suggests the dataset captures high-frequency snapshot telemetry rather than continuous match recordings. Playback functionality remains meaningful regardless of unit, since `ts_relative` provides a consistent within-match ordering — the slider scrubs from match start to end on the data's own time axis.

**Heatmap scope.** Heatmap aggregations intentionally ignore single-match selection, since aggregate views require many data points to convey meaningful patterns. They respect map, date, and multi-player filters, which produce population-level views rather than per-game ones.

## Engineering Tradeoffs

Each significant design decision involved a deliberate tradeoff. The most important ones are summarized below.

| Decision | Choice | Tradeoff Accepted |
|---|---|---|
| Data preprocessing strategy | Pre-computed parquet files committed to the repository | Updating the dataset requires re-running the preprocessing script. Acceptable given the dataset is fixed. |
| Position event sampling | Every 3rd row retained (3x downsampling) | Path resolution is slightly reduced. Visually imperceptible at typical zoom levels. |
| Visualization library | Plotly over custom canvas | Less granular visual control. Gained: full interactivity, hover, and legend toggles without custom code. |
| Per-player coloring scope | Applied only in single-match mode (≤8 humans) | Multi-match views cannot distinguish individual players. With hundreds of overlapping paths, distinguishing them would be visually counterproductive anyway. |
| Heatmap rendering modes | Two styles offered: Glow points (default) and Density grid | Adds modest UI surface. Each style serves a different perceptual need. |
| Playback animation mechanism | Streamlit script reruns on a 100ms tick | Slider position updates in discrete steps rather than gliding smoothly. Avoids the complexity of WebSockets or custom JavaScript animation. |
| Minimap distribution | PNG files committed to the repository | Repository size increases by approximately 5 MB. Eliminates external asset hosting. |

## Out of Scope

The following capabilities were considered but excluded to remain within the project budget:

- **Per-match heatmaps** would require fundamentally different rendering due to data sparsity. Cross-match heatmaps were prioritized as the use case where heatmap visualization adds the most analytical value.
- **Custom UI theming beyond Streamlit's defaults** was deprioritized in favor of feature completeness, consistent with the brief's "quality over quantity" guidance.
- **Match comparison mode** (side-by-side viewing of multiple matches) is conceptually valuable but lies outside the explicit core requirements.