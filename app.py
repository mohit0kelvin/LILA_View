"""
LILA BLACK - Player Journey Visualizer

Phase 3: Basic map rendering with all events on AmbroseValley.
Filters and interactivity come in Phase 4.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from PIL import Image

from utils import MAP_CONFIGS, MINIMAP_PATHS, get_minimap_size, world_to_pixel


# ---------- Page setup ----------

st.set_page_config(
    page_title="LILA BLACK Visualizer",
    page_icon="🎮",
    layout="wide",  # use full browser width
)

st.title("🎮 LILA BLACK — Player Journey Visualizer")
st.caption("Telemetry visualization for the Level Design team")


# ---------- Data loading (cached so it only happens once per session) ----------

@st.cache_data
def load_events() -> pd.DataFrame:
    return pd.read_parquet("data/processed/events.parquet")

@st.cache_data
def load_paths() -> pd.DataFrame:
    return pd.read_parquet("data/processed/paths.parquet")

@st.cache_data
def load_matches() -> pd.DataFrame:
    return pd.read_parquet("data/processed/matches.parquet")

events = load_events()
paths = load_paths()
matches = load_matches()


# ---------- For Phase 3: hardcode to AmbroseValley to prove rendering works ----------

selected_map = "AmbroseValley"

# Filter data to this map
map_events = events[events['map_id'] == selected_map]
map_paths = paths[paths['map_id'] == selected_map]

st.markdown(f"**Map:** {selected_map}  |  **Events:** {len(map_events):,}  |  **Path samples:** {len(map_paths):,}")


# ---------- Build the visualization ----------

# Get minimap and its actual dimensions
minimap = Image.open(MINIMAP_PATHS[selected_map])
img_w, img_h = minimap.size

# Convert all events' world coords to pixel coords using the utility
def add_pixels(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    pixels = df.apply(
        lambda row: world_to_pixel(row['x'], row['z'], selected_map, img_w, img_h),
        axis=1
    )
    df['px'] = [p[0] for p in pixels]
    df['py'] = [p[1] for p in pixels]
    return df

map_events = add_pixels(map_events)
map_paths = add_pixels(map_paths)

# Visual style for each event type. Designed to be distinct at a glance.
EVENT_STYLES = {
    'Loot':          {'color': '#FFD700', 'symbol': 'square',         'size': 6,  'name': 'Loot'},
    'Kill':          {'color': '#FF1744', 'symbol': 'x',              'size': 16, 'name': 'Human kill'},
    'Killed':        {'color': '#FF1744', 'symbol': 'circle',         'size': 12, 'name': 'Human killed'},
    'BotKill':       {'color': '#FF9800', 'symbol': 'x',              'size': 10, 'name': 'Bot kill'},
    'BotKilled':     {'color': '#E040FB', 'symbol': 'circle',         'size': 10, 'name': 'Killed by bot'},
    'KilledByStorm': {'color': '#9C27B0', 'symbol': 'triangle-up',    'size': 14, 'name': 'Storm death'},
}

# Build the figure
fig = go.Figure()

# Layer 1: minimap as background image
fig.add_layout_image(
    dict(
        source=minimap,
        xref="x",
        yref="y",
        x=0, y=0,
        sizex=img_w, sizey=img_h,
        sizing="stretch",
        layer="below",
    )
)

# Layer 2: position trails (cyan, very light)
human_paths = map_paths[map_paths['is_human']]
bot_paths = map_paths[~map_paths['is_human']]

fig.add_trace(go.Scatter(
    x=bot_paths['px'], y=bot_paths['py'],
    mode='markers',
    marker=dict(size=2, color='gray', opacity=0.15),
    name=f"Bot positions ({len(bot_paths):,})",
    hoverinfo='skip',
))

fig.add_trace(go.Scatter(
    x=human_paths['px'], y=human_paths['py'],
    mode='markers',
    marker=dict(size=2, color='cyan', opacity=0.20),
    name=f"Human positions ({len(human_paths):,})",
    hoverinfo='skip',
))

# Layer 3: combat & loot events on top
for event_type, style in EVENT_STYLES.items():
    subset = map_events[map_events['event'] == event_type]
    if len(subset) == 0:
        continue
    fig.add_trace(go.Scatter(
        x=subset['px'], y=subset['py'],
        mode='markers',
        marker=dict(
            size=style['size'],
            color=style['color'],
            symbol=style['symbol'],
            line=dict(width=0.5, color='black'),
        ),
        name=f"{style['name']} ({len(subset)})",
        hovertemplate=(
            "<b>%{text}</b><br>"
            "World: (%{customdata[0]:.0f}, %{customdata[1]:.0f})<br>"
            "<extra></extra>"
        ),
        text=[event_type] * len(subset),
        customdata=subset[['x', 'z']].values,
    ))

# Configure the layout: lock aspect ratio, hide axes, make it big
fig.update_xaxes(
    range=[0, img_w], showgrid=False, zeroline=False,
    showticklabels=False, visible=False,
)
fig.update_yaxes(
    range=[img_h, 0],  # invert Y to match image coords
    scaleanchor="x", scaleratio=1,  # lock aspect ratio
    showgrid=False, zeroline=False,
    showticklabels=False, visible=False,
)

fig.update_layout(
    height=800,
    margin=dict(l=0, r=0, t=0, b=0),
    legend=dict(
        bgcolor="rgba(0,0,0,0.6)",
        bordercolor="rgba(255,255,255,0.2)",
        borderwidth=1,
        font=dict(color="white"),
        x=0.01, y=0.99,
    ),
    plot_bgcolor='black',
    paper_bgcolor='black',
)

st.plotly_chart(fig, use_container_width=True)


# ---------- Quick stats panel ----------

with st.expander("Quick stats for this map"):
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total events", f"{len(map_events):,}")
    col2.metric("Position samples", f"{len(map_paths):,}")
    col3.metric("Matches on this map", matches[matches['map_id'] == selected_map].shape[0])
    col4.metric("Unique players", map_events['user_id'].nunique())