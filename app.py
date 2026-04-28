"""
LILA BLACK - Player Journey Visualizer

Phases 3-6 combined:
- Map rendering with all event types (Phase 3)
- Sidebar filters (map, date, match, multi-player toggle, layer toggles) (Phase 4)
- Per-player coloring + visible bot paths in single-match mode (Phase 4)
- Timeline playback for individual matches (Phase 5)
- Heatmap view with Kill zones / Death zones / Traffic (Phase 6)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from PIL import Image
import time

from utils import MAP_CONFIGS, MINIMAP_PATHS, world_to_pixel


# ---------- Page setup ----------

st.set_page_config(
    page_title="LILA BLACK Visualizer",
    page_icon="🎮",
    layout="wide",
)

st.title("🎮 LILA BLACK — Player Journey Visualizer")
st.caption("Telemetry visualization for the Level Design team")


# ---------- Data loading (cached) ----------

@st.cache_data
def load_events() -> pd.DataFrame:
    return pd.read_parquet("data/processed/events.parquet")

@st.cache_data
def load_paths() -> pd.DataFrame:
    return pd.read_parquet("data/processed/paths.parquet")

@st.cache_data
def load_matches() -> pd.DataFrame:
    return pd.read_parquet("data/processed/matches.parquet")

@st.cache_data
def load_minimap(map_id: str):
    return Image.open(MINIMAP_PATHS[map_id])

events = load_events()
paths = load_paths()
matches = load_matches()


# ---------- SIDEBAR: Filters ----------

st.sidebar.header("🎯 Filters")

# Map
selected_map = st.sidebar.selectbox(
    "Map",
    options=list(MAP_CONFIGS.keys()),
    index=0,
)

# Date
date_options = ["All days"] + sorted(matches['date'].unique().tolist())
date_labels = [d if d != "2026-02-14" else "2026-02-14 (partial)" for d in date_options]
selected_date_label = st.sidebar.selectbox(
    "Date",
    options=date_labels,
    index=0,
)
selected_date = (
    None if selected_date_label == "All days"
    else selected_date_label.replace(" (partial)", "")
)

# Multi-player toggle
multi_player_only = st.sidebar.checkbox(
    "Multi-player matches only (5+ files)",
    value=False,
    help=(
        "Hides single-file matches (743 of 796 matches have only 1 file — likely lone-wolf, "
        "test, or disengaged sessions). Note: ALL 39 storm deaths in the dataset occur in "
        "single-file matches, so turn this filter ON only when you want to focus on real "
        "multi-player engagements."
    )
)

# Match selector
filtered_matches = matches[matches['map_id'] == selected_map]
if selected_date is not None:
    filtered_matches = filtered_matches[filtered_matches['date'] == selected_date]
if multi_player_only:
    filtered_matches = filtered_matches[filtered_matches['n_files'] >= 5]


def match_label(row):
    short_id = row['match_id'][:8]
    return (f"{short_id}... ({row['n_humans']}H + {row['n_bots']}B, "
            f"{row['n_events_total']} events)")

match_options = ["All matches"] + [
    match_label(row) for _, row in filtered_matches.iterrows()
]
selected_match_label = st.sidebar.selectbox(
    f"Match ({len(filtered_matches)} available)",
    options=match_options,
    index=0,
)

if selected_match_label == "All matches":
    selected_match_id = None
else:
    short_id = selected_match_label.split("...")[0]
    matching = filtered_matches[filtered_matches['match_id'].str.startswith(short_id)]
    selected_match_id = matching['match_id'].iloc[0] if len(matching) else None

# Layer toggles
st.sidebar.markdown("---")
st.sidebar.subheader("👁️ Layers (Markers View)")
show_human_paths = st.sidebar.checkbox("Human paths", value=True)
show_bot_paths = st.sidebar.checkbox("Bot paths", value=False)
show_loot = st.sidebar.checkbox("Loot", value=True)
show_kills = st.sidebar.checkbox("Kills (human)", value=True)
show_killed = st.sidebar.checkbox("Killed (human died)", value=True)
show_bot_kills = st.sidebar.checkbox("Bot kills", value=True)
show_bot_killed = st.sidebar.checkbox("Killed by bot", value=True)
show_storm = st.sidebar.checkbox("Storm deaths", value=True)


# ---------- Apply filters to data ----------

filt_events = events[events['map_id'] == selected_map]
filt_paths = paths[paths['map_id'] == selected_map]

if selected_date is not None:
    filt_events = filt_events[filt_events['date'] == selected_date]
    filt_paths = filt_paths[filt_paths['date'] == selected_date]

if selected_match_id is not None:
    filt_events = filt_events[filt_events['match_id'] == selected_match_id]
    filt_paths = filt_paths[filt_paths['match_id'] == selected_match_id]
else:
    if multi_player_only:
        valid_match_ids = filtered_matches['match_id'].tolist()
        filt_events = filt_events[filt_events['match_id'].isin(valid_match_ids)]
        filt_paths = filt_paths[filt_paths['match_id'].isin(valid_match_ids)]


# ---------- MINIMAP & COORDINATE TRANSFORM (shared by both tabs) ----------

minimap = load_minimap(selected_map)
img_w, img_h = minimap.size


def add_pixels(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) == 0:
        return df.assign(px=[], py=[])
    df = df.copy()
    pixels = df.apply(
        lambda row: world_to_pixel(row['x'], row['z'], selected_map, img_w, img_h),
        axis=1
    )
    df['px'] = [p[0] for p in pixels]
    df['py'] = [p[1] for p in pixels]
    return df


# ---------- Header bar ----------

n_matches_shown = (
    1 if selected_match_id is not None
    else len(filtered_matches)
)
st.markdown(
    f"**Map:** {selected_map}  |  "
    f"**Matches shown:** {n_matches_shown}  |  "
    f"**Events:** {len(filt_events):,}  |  "
    f"**Path samples:** {len(filt_paths):,}"
)


# ---------- TABS: MARKERS VIEW vs HEATMAP VIEW ----------

tab_markers, tab_heatmap = st.tabs(["📍 Markers View", "🔥 Heatmap View"])


# ============================================================================
#  MARKERS VIEW (everything from Phase 3-5)
# ============================================================================
with tab_markers:
    filt_events_marker = add_pixels(filt_events)
    filt_paths_marker = add_pixels(filt_paths)

    # ---------- TIMELINE PLAYBACK CONTROLS ----------

    playback_active = (selected_match_id is not None) and (
        len(filt_events_marker) > 0 or len(filt_paths_marker) > 0
    )
    ts_min, ts_max = 0, 0

    if playback_active:
        all_match_rows = pd.concat([
            filt_events_marker[['ts_relative']],
            filt_paths_marker[['ts_relative']]
        ], ignore_index=True)
        if len(all_match_rows) == 0:
            playback_active = False

    if playback_active:
        ts_min = int(all_match_rows['ts_relative'].min())
        ts_max = int(all_match_rows['ts_relative'].max())
        total_events_in_match = len(filt_events_marker) + len(filt_paths_marker)

        if ts_max <= ts_min:
            playback_active = False
            st.markdown("### ⏯️ Match Playback")
            st.info(
                f"⏸️ This match has all {total_events_in_match} events at the same timestamp "
                f"(ts = {ts_min}). Playback is disabled — the full match is shown below."
            )
        else:
            if 'playback_ts' not in st.session_state:
                st.session_state.playback_ts = ts_max
            if 'is_playing' not in st.session_state:
                st.session_state.is_playing = False
            if 'playback_speed' not in st.session_state:
                st.session_state.playback_speed = 1.0
            if ('last_match_id' not in st.session_state
                    or st.session_state.last_match_id != selected_match_id):
                st.session_state.playback_ts = ts_max
                st.session_state.is_playing = False
                st.session_state.last_match_id = selected_match_id

            st.markdown("### ⏯️ Match Playback")

            btn_col1, btn_col2, btn_col3, speed_col, _ = st.columns([1, 1, 1, 2, 5])

            with btn_col1:
                if st.button("⏮️ Reset", help="Reset to start", use_container_width=True):
                    st.session_state.playback_ts = ts_min
                    st.session_state.is_playing = False
                    st.session_state.slider_version = st.session_state.get('slider_version', 0) + 1
                    st.rerun()

            with btn_col2:
                if not st.session_state.is_playing:
                    if st.button("▶️ Play", help="Play", use_container_width=True):
                        if st.session_state.playback_ts >= ts_max:
                            st.session_state.playback_ts = ts_min
                            st.session_state.slider_version = st.session_state.get('slider_version', 0) + 1
                        st.session_state.is_playing = True
                        st.rerun()
                else:
                    if st.button("⏸️ Pause", help="Pause", use_container_width=True):
                        st.session_state.is_playing = False
                        st.rerun()

            with btn_col3:
                if st.button("⏭️ End", help="Jump to end", use_container_width=True):
                    st.session_state.playback_ts = ts_max
                    st.session_state.is_playing = False
                    st.session_state.slider_version = st.session_state.get('slider_version', 0) + 1
                    st.rerun()

            with speed_col:
                st.session_state.playback_speed = st.selectbox(
                    "Speed",
                    options=[0.5, 1.0, 2.0, 4.0],
                    index=[0.5, 1.0, 2.0, 4.0].index(st.session_state.playback_speed),
                    format_func=lambda x: f"{x}x",
                    label_visibility="collapsed",
                )

            slider_version = st.session_state.get('slider_version', 0)
            playback_ts = st.slider(
                "Playback time",
                min_value=ts_min,
                max_value=ts_max,
                value=int(st.session_state.playback_ts),
                step=max(1, (ts_max - ts_min) // 200),
                label_visibility="collapsed",
                key=f'playback_slider_v{slider_version}',
            )
            if playback_ts != st.session_state.playback_ts and not st.session_state.get('is_playing', False):
                st.session_state.playback_ts = playback_ts

            n_visible_events = (filt_events_marker['ts_relative'] <= st.session_state.playback_ts).sum()
            n_visible_paths = (filt_paths_marker['ts_relative'] <= st.session_state.playback_ts).sum()
            n_visible_total = n_visible_events + n_visible_paths
            st.caption(
                f"📍 Event {n_visible_total} of {total_events_in_match}  "
                f"|  ts: {int(st.session_state.playback_ts)}ms / {ts_max}ms"
            )

            filt_events_marker = filt_events_marker[
                filt_events_marker['ts_relative'] <= st.session_state.playback_ts
            ]
            filt_paths_marker = filt_paths_marker[
                filt_paths_marker['ts_relative'] <= st.session_state.playback_ts
            ]
    else:
        if 'is_playing' in st.session_state:
            st.session_state.is_playing = False

    # ---------- Build the markers visualization ----------

    n_humans_visible = (
        filt_paths_marker[filt_paths_marker['is_human']]['user_id'].nunique()
        if len(filt_paths_marker) else 0
    )
    single_match_mode = (selected_match_id is not None) or n_humans_visible <= 8

    PLAYER_PALETTE = [
        '#00E5FF', '#FFEA00', '#76FF03', '#F50057', '#651FFF',
        '#FF6E40', '#1DE9B6', '#FF4081', '#7C4DFF', '#FFAB00',
        '#69F0AE', '#E040FB', '#40C4FF', '#FF8A65', '#B2FF59',
        '#FFD740', '#536DFE', '#FF80AB', '#84FFFF', '#EEFF41',
        '#FF5252', '#A7FFEB', '#B388FF', '#FFAB91',
    ]
    BOT_PALETTE = [
        '#FFA726', '#A1887F', '#90A4AE', '#BCAAA4',
        '#9E9D24', '#8D6E63', '#78909C', '#6D4C41',
        '#827717', '#5D4037', '#455A64', '#4E342E',
        '#33691E', '#3E2723', '#263238', '#1B5E20',
    ]

    def _connect_per_user(df: pd.DataFrame, col: str) -> list:
        if len(df) == 0:
            return []
        out = []
        last_user = None
        for user_id, value in zip(df['user_id'].values, df[col].values):
            if last_user is not None and user_id != last_user:
                out.append(None)
            out.append(value)
            last_user = user_id
        return out

    fig = go.Figure()
    fig.add_layout_image(
        dict(
            source=minimap, xref="x", yref="y",
            x=0, y=0, sizex=img_w, sizey=img_h,
            sizing="stretch", layer="below",
        )
    )

    human_paths_df = filt_paths_marker[filt_paths_marker['is_human']].sort_values(['user_id', 'ts_ms'])
    bot_paths_df = filt_paths_marker[~filt_paths_marker['is_human']].sort_values(['user_id', 'ts_ms'])

    EVENT_STYLES = {
        'Loot':          {'symbol': 'diamond',     'size': 14, 'name': 'Loot',         'show_var': 'show_loot'},
        'Kill':          {'symbol': 'x',           'size': 24, 'name': 'Human kill',   'show_var': 'show_kills'},
        'Killed':        {'symbol': 'cross',       'size': 24, 'name': 'Human killed', 'show_var': 'show_killed'},
        'BotKill':       {'symbol': 'x',           'size': 18, 'name': 'Bot kill',     'show_var': 'show_bot_kills'},
        'BotKilled':     {'symbol': 'cross',       'size': 18, 'name': 'Killed by bot','show_var': 'show_bot_killed'},
        'KilledByStorm': {'symbol': 'triangle-up', 'size': 22, 'name': 'Storm death',  'show_var': 'show_storm'},
    }
    DEFAULT_EVENT_COLORS = {
        'Loot':          '#FFD700',
        'Kill':          '#FF1744',
        'Killed':        '#FF1744',
        'BotKill':       '#FF9800',
        'BotKilled':     '#E040FB',
        'KilledByStorm': '#9C27B0',
    }
    LAYER_FLAGS = {
        'show_loot': show_loot,
        'show_kills': show_kills,
        'show_killed': show_killed,
        'show_bot_kills': show_bot_kills,
        'show_bot_killed': show_bot_killed,
        'show_storm': show_storm,
    }

    # Bot paths
    if show_bot_paths and len(bot_paths_df) > 0:
        if single_match_mode:
            unique_bots = sorted(bot_paths_df['user_id'].unique().tolist())
            bot_colors = {bid: BOT_PALETTE[i % len(BOT_PALETTE)] for i, bid in enumerate(unique_bots)}
            for bid in unique_bots:
                bdf = bot_paths_df[bot_paths_df['user_id'] == bid]
                if len(bdf) == 0:
                    continue
                fig.add_trace(go.Scatter(
                    x=bdf['px'], y=bdf['py'],
                    mode='lines+markers',
                    line=dict(color=bot_colors[bid], width=2, dash='dot'),
                    marker=dict(size=8, color=bot_colors[bid], opacity=0.7,
                                line=dict(width=1, color='black')),
                    opacity=0.6,
                    name=f"Bot-{bid}",
                    hovertemplate=f"<b>Bot {bid}</b><br>Position<extra></extra>",
                ))
        else:
            fig.add_trace(go.Scatter(
                x=_connect_per_user(bot_paths_df, 'px'),
                y=_connect_per_user(bot_paths_df, 'py'),
                mode='lines',
                line=dict(color='gray', width=1),
                opacity=0.15,
                name=f"Bot paths ({bot_paths_df['user_id'].nunique()} bots)",
                hoverinfo='skip',
            ))

    # Human paths + events
    if single_match_mode and n_humans_visible > 0:
        unique_humans = sorted(human_paths_df['user_id'].unique().tolist())
        player_colors = {uid: PLAYER_PALETTE[i % len(PLAYER_PALETTE)] for i, uid in enumerate(unique_humans)}

        for uid in unique_humans:
            if not show_human_paths:
                break
            pdf = human_paths_df[human_paths_df['user_id'] == uid]
            if len(pdf) == 0:
                continue
            their_events = filt_events_marker[filt_events_marker['user_id'] == uid]
            n_loot = (their_events['event'] == 'Loot').sum()
            n_kills = ((their_events['event'] == 'Kill') | (their_events['event'] == 'BotKill')).sum()
            died = (their_events['event'].isin(['Killed', 'BotKilled', 'KilledByStorm'])).any()
            death_emoji = " 💀" if died else ""

            fig.add_trace(go.Scatter(
                x=pdf['px'], y=pdf['py'],
                mode='lines+markers',
                line=dict(color=player_colors[uid], width=3),
                marker=dict(size=14, color=player_colors[uid], opacity=0.9,
                            line=dict(width=1.5, color='black')),
                opacity=0.95,
                name=f"P-{uid[:6]} ({n_kills}K {n_loot}L){death_emoji}",
                hovertemplate=f"<b>Player {uid[:8]}</b><br>Position<extra></extra>",
            ))
            if len(pdf) > 0:
                start = pdf.iloc[0]
                fig.add_trace(go.Scatter(
                    x=[start['px']], y=[start['py']],
                    mode='markers',
                    marker=dict(size=18, color=player_colors[uid], symbol='star',
                                line=dict(width=2, color='white')),
                    name=None, showlegend=False,
                    hovertemplate=f"<b>Start: Player {uid[:8]}</b><extra></extra>",
                ))

        for event_type, style in EVENT_STYLES.items():
            if not LAYER_FLAGS[style['show_var']]:
                continue
            for uid in unique_humans:
                subset = filt_events_marker[
                    (filt_events_marker['event'] == event_type) & (filt_events_marker['user_id'] == uid)
                ]
                if len(subset) == 0:
                    continue
                fig.add_trace(go.Scatter(
                    x=subset['px'], y=subset['py'],
                    mode='markers',
                    marker=dict(size=style['size'], color=player_colors[uid],
                                symbol=style['symbol'], line=dict(width=2, color='white')),
                    name=None, showlegend=False,
                    hovertemplate=(
                        f"<b>{style['name']}</b><br>Player: {uid[:8]}<br>"
                        "World: (%{customdata[0]:.0f}, %{customdata[1]:.0f})<extra></extra>"
                    ),
                    customdata=subset[['x', 'z']].values,
                ))
    else:
        if show_human_paths and len(human_paths_df) > 0:
            fig.add_trace(go.Scatter(
                x=_connect_per_user(human_paths_df, 'px'),
                y=_connect_per_user(human_paths_df, 'py'),
                mode='lines',
                line=dict(color='cyan', width=1),
                opacity=0.35,
                name=f"Human paths ({human_paths_df['user_id'].nunique()} players)",
                hoverinfo='skip',
            ))
        for event_type, style in EVENT_STYLES.items():
            if not LAYER_FLAGS[style['show_var']]:
                continue
            subset = filt_events_marker[filt_events_marker['event'] == event_type]
            if len(subset) == 0:
                continue
            fig.add_trace(go.Scatter(
                x=subset['px'], y=subset['py'],
                mode='markers',
                marker=dict(size=style['size'], color=DEFAULT_EVENT_COLORS[event_type],
                            symbol=style['symbol'], line=dict(width=0.5, color='black')),
                name=f"{style['name']} ({len(subset)})",
                hovertemplate=(
                    f"<b>{style['name']}</b><br>"
                    "World: (%{customdata[0]:.0f}, %{customdata[1]:.0f})<extra></extra>"
                ),
                customdata=subset[['x', 'z']].values,
            ))

    fig.update_xaxes(range=[0, img_w], showgrid=False, zeroline=False,
                     showticklabels=False, visible=False)
    fig.update_yaxes(range=[img_h, 0], scaleanchor="x", scaleratio=1,
                     showgrid=False, zeroline=False, showticklabels=False, visible=False)
    fig.update_layout(
        height=800,
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(bgcolor="rgba(0,0,0,0.6)", bordercolor="rgba(255,255,255,0.2)",
                    borderwidth=1, font=dict(color="white"), x=0.01, y=0.99),
        plot_bgcolor='black',
        paper_bgcolor='black',
    )

    if single_match_mode and n_humans_visible > 0:
        st.caption(
            "**Symbols:** ⭐ start  ●  position  ◆ loot  ✕ kill  ✚ killed  ▲ storm death  "
            "— Each player has a unique color. Hover any marker for details."
        )

    if len(filt_events_marker) == 0 and len(filt_paths_marker) == 0:
        st.info("No events match the current filters. Try widening your selection.")
    else:
        st.plotly_chart(fig, use_container_width=True, key="markers_chart")


# ============================================================================
#  HEATMAP VIEW
# ============================================================================
with tab_heatmap:
    if selected_match_id is not None:
        st.info(
            "📊 Heatmap is most useful in **'All matches' mode** — single-match data is too "
            "sparse for a meaningful heat distribution. Try setting **Match → All matches** "
            "in the sidebar."
        )

    heatmap_col1, heatmap_col2 = st.columns([3, 2])

    with heatmap_col1:
        heatmap_type = st.radio(
            "Show heatmap of:",
            options=["Kill zones", "Death zones", "Traffic"],
            horizontal=True,
            help=(
                "Kill zones: where humans/bots scored kills.  |  "
                "Death zones: where players/bots died.  |  "
                "Traffic: where players moved."
            ),
        )

    with heatmap_col2:
        heatmap_style = st.radio(
            "Style:",
            options=["Glow points", "Density grid"],
            horizontal=True,
            help=(
                "Glow points: each event shown as a translucent glow (cleaner, respects map shape). "
                "Density grid: traditional heatmap with binned regions (more familiar but rectangular)."
            ),
        )

    # For heatmap, use map+date+multi-player filtered data BUT ignore match selection
    heat_events = events[events['map_id'] == selected_map]
    heat_paths = paths[paths['map_id'] == selected_map]
    if selected_date is not None:
        heat_events = heat_events[heat_events['date'] == selected_date]
        heat_paths = heat_paths[heat_paths['date'] == selected_date]
    if multi_player_only:
        valid_match_ids = filtered_matches['match_id'].tolist()
        heat_events = heat_events[heat_events['match_id'].isin(valid_match_ids)]
        heat_paths = heat_paths[heat_paths['match_id'].isin(valid_match_ids)]

    # Pick the right subset
    if heatmap_type == "Kill zones":
        heat_data = heat_events[heat_events['event'].isin(['Kill', 'BotKill'])]
        glow_color = '#FF1744'  # red
        density_label = "Kills"
        gradient_colorscale = [
            [0.0, 'rgba(0,0,0,0)'],
            [0.3, 'rgba(255,180,0,0.4)'],
            [0.6, 'rgba(255,80,0,0.7)'],
            [1.0, 'rgba(255,0,0,1.0)'],
        ]
    elif heatmap_type == "Death zones":
        heat_data = heat_events[heat_events['event'].isin(['Killed', 'BotKilled', 'KilledByStorm'])]
        glow_color = '#E040FB'  # magenta
        density_label = "Deaths"
        gradient_colorscale = [
            [0.0, 'rgba(0,0,0,0)'],
            [0.3, 'rgba(180,100,200,0.4)'],
            [0.6, 'rgba(220,50,180,0.7)'],
            [1.0, 'rgba(255,0,200,1.0)'],
        ]
    else:  # Traffic
        heat_data = heat_paths
        glow_color = '#00E5FF'  # cyan
        density_label = "Position samples"
        gradient_colorscale = [
            [0.0, 'rgba(0,0,0,0)'],
            [0.3, 'rgba(0,200,255,0.4)'],
            [0.6, 'rgba(0,255,180,0.7)'],
            [1.0, 'rgba(255,255,0,1.0)'],
        ]

    heat_data = add_pixels(heat_data)

    st.markdown(
        f"**Showing:** {heatmap_type}  |  "
        f"**Style:** {heatmap_style}  |  "
        f"**Data points:** {len(heat_data):,}"
    )

    if len(heat_data) < 5:
        st.warning(
            f"Too few data points ({len(heat_data)}) for a meaningful heatmap. "
            "Try 'All days' or turn off multi-player toggle."
        )
    else:
        fig_heat = go.Figure()
        fig_heat.add_layout_image(
            dict(
                source=minimap, xref="x", yref="y",
                x=0, y=0, sizex=img_w, sizey=img_h,
                sizing="stretch", layer="below",
            )
        )

        if heatmap_style == "Glow points":
            # Render each event as a translucent glow point. Multiple overlapping points
            # naturally create heat zones. Cleaner than binned heatmaps and respects map shape.

            # Adapt point size to the map's image size so it looks right at any scale
            base_size = max(img_w, img_h) // 60

            # For traffic data (large volume), use smaller and more transparent points
            if heatmap_type == "Traffic":
                point_size = max(8, base_size // 2)
                point_opacity = 0.04
            else:
                point_size = base_size
                point_opacity = 0.25

            fig_heat.add_trace(go.Scatter(
                x=heat_data['px'],
                y=heat_data['py'],
                mode='markers',
                marker=dict(
                    size=point_size,
                    color=glow_color,
                    opacity=point_opacity,
                    line=dict(width=0),
                ),
                name=density_label,
                hoverinfo='skip',
            ))

            # Add a second tighter layer at higher opacity for the brightest hotspots
            fig_heat.add_trace(go.Scatter(
                x=heat_data['px'],
                y=heat_data['py'],
                mode='markers',
                marker=dict(
                    size=max(4, point_size // 2),
                    color=glow_color,
                    opacity=min(0.5, point_opacity * 4),
                    line=dict(width=0),
                ),
                name=f"{density_label} (core)",
                hoverinfo='skip',
                showlegend=False,
            ))
        else:
            # Density grid (traditional binned heatmap)
            n_bins = 60 if heatmap_type == "Traffic" else 35
            fig_heat.add_trace(go.Histogram2d(
                x=heat_data['px'],
                y=heat_data['py'],
                colorscale=gradient_colorscale,
                nbinsx=n_bins,
                nbinsy=n_bins,
                xbins=dict(start=0, end=img_w),
                ybins=dict(start=0, end=img_h),
                opacity=0.85,
                colorbar=dict(title=density_label, thickness=15),
                zmin=1,  # hide empty bins
                zauto=True,
                hoverinfo='skip',
            ))

        fig_heat.update_xaxes(range=[0, img_w], showgrid=False, zeroline=False,
                              showticklabels=False, visible=False)
        fig_heat.update_yaxes(range=[img_h, 0], scaleanchor="x", scaleratio=1,
                              showgrid=False, zeroline=False, showticklabels=False, visible=False)
        fig_heat.update_layout(
            height=800,
            margin=dict(l=0, r=0, t=0, b=0),
            plot_bgcolor='black',
            paper_bgcolor='black',
            showlegend=False,
        )

        st.plotly_chart(fig_heat, use_container_width=True, key="heatmap_chart")

# ---------- Stats panel (under both tabs) ----------

with st.expander("📊 Stats for current selection"):
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Matches", n_matches_shown)
    col2.metric("Events shown", f"{len(filt_events):,}")
    col3.metric("Path samples", f"{len(filt_paths):,}")
    col4.metric("Unique players", filt_events['user_id'].nunique() if len(filt_events) else 0)

    if selected_match_id is not None:
        match_row = matches[matches['match_id'] == selected_match_id].iloc[0]
        st.markdown("**Selected match details:**")
        st.json({
            "match_id": match_row['match_id'],
            "map": match_row['map_id'],
            "date": match_row['date'],
            "humans": int(match_row['n_humans']),
            "bots": int(match_row['n_bots']),
            "kills (human-vs-human)": int(match_row['n_kills']),
            "bot kills (human killed bot)": int(match_row['n_bot_kills']),
            "killed by bot": int(match_row['n_bot_killed']),
            "storm deaths": int(match_row['n_storm_deaths']),
            "loot pickups": int(match_row['n_loot']),
            "match duration (ms)": int(match_row['duration_ms']),
        })


# ---------- AUTO-ADVANCE PLAYBACK ----------

if 'is_playing' in st.session_state and st.session_state.is_playing and 'playback_ts' in st.session_state:
    if 'last_match_id' in st.session_state and st.session_state.last_match_id == selected_match_id:
        # Make sure we have valid bounds
        if selected_match_id is not None:
            match_data = pd.concat([
                events[events['match_id'] == selected_match_id][['ts_relative']],
                paths[paths['match_id'] == selected_match_id][['ts_relative']]
            ], ignore_index=True)
            if len(match_data) > 0:
                local_ts_min = int(match_data['ts_relative'].min())
                local_ts_max = int(match_data['ts_relative'].max())
                if local_ts_max > local_ts_min:
                    if st.session_state.playback_ts >= local_ts_max:
                        st.session_state.is_playing = False
                        st.rerun()
                    else:
                        step = max(1, (local_ts_max - local_ts_min) // 50)
                        scaled_step = int(step * st.session_state.playback_speed)
                        next_ts = min(local_ts_max, st.session_state.playback_ts + scaled_step)
                        time.sleep(0.1)
                        st.session_state.playback_ts = next_ts
                        st.session_state.slider_version = st.session_state.get('slider_version', 0) + 1
                        st.rerun()