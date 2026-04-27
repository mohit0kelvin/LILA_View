"""
LILA BLACK - Player Journey Visualizer

Phase 4: Sidebar filters for map, date, match, and event layers.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from PIL import Image

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
    """Load and cache the minimap image (PIL Image object)."""
    return Image.open(MINIMAP_PATHS[map_id])

events = load_events()
paths = load_paths()
matches = load_matches()


# ---------- SIDEBAR: Filters ----------

st.sidebar.header("🎯 Filters")

# --- Map filter ---
selected_map = st.sidebar.selectbox(
    "Map",
    options=list(MAP_CONFIGS.keys()),
    index=0,  # default: AmbroseValley
)

# --- Date filter ---
date_options = ["All days"] + sorted(matches['date'].unique().tolist())
# Label Feb 14 as partial
date_labels = [d if d != "2026-02-14" else "2026-02-14 (partial)" for d in date_options]
selected_date_label = st.sidebar.selectbox(
    "Date",
    options=date_labels,
    index=0,
)
# Convert label back to actual date string
selected_date = (
    None if selected_date_label == "All days"
    else selected_date_label.replace(" (partial)", "")
)

# --- Multi-player only toggle ---
multi_player_only = st.sidebar.checkbox(
    "Multi-player matches only (5+ files)",
    value=False,  # default OFF so users see the full dataset, including storm-death matches
    help=(
        "Hides single-file matches (743 of 796 matches have only 1 file — likely lone-wolf, "
        "test, or disengaged sessions). Note: ALL 39 storm deaths in the dataset occur in "
        "single-file matches, so turn this filter ON only when you want to focus on real "
        "multi-player engagements."
    )
)
# --- Match selector (filtered by map + date + multi-player) ---
filtered_matches = matches[matches['map_id'] == selected_map]
if selected_date is not None:
    filtered_matches = filtered_matches[filtered_matches['date'] == selected_date]
if multi_player_only:
    filtered_matches = filtered_matches[filtered_matches['n_files'] >= 5]

# Build label strings: "Match abc12345... (5 humans, 12 bots, 423 events)"
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

# Convert label back to actual match_id
if selected_match_label == "All matches":
    selected_match_id = None
else:
    short_id = selected_match_label.split("...")[0]
    matching = filtered_matches[filtered_matches['match_id'].str.startswith(short_id)]
    selected_match_id = matching['match_id'].iloc[0] if len(matching) else None

# --- Layer toggles ---
st.sidebar.markdown("---")
st.sidebar.subheader("👁️ Layers")
show_human_paths = st.sidebar.checkbox("Human paths", value=True)
show_bot_paths = st.sidebar.checkbox("Bot paths", value=False)
show_loot = st.sidebar.checkbox("Loot", value=True)
show_kills = st.sidebar.checkbox("Kills (human)", value=True)
show_killed = st.sidebar.checkbox("Killed (human died)", value=True)
show_bot_kills = st.sidebar.checkbox("Bot kills", value=True)
show_bot_killed = st.sidebar.checkbox("Killed by bot", value=True)
show_storm = st.sidebar.checkbox("Storm deaths", value=True)


# ---------- Apply filters to data ----------

# Filter events
filt_events = events[events['map_id'] == selected_map]
filt_paths = paths[paths['map_id'] == selected_map]

if selected_date is not None:
    filt_events = filt_events[filt_events['date'] == selected_date]
    filt_paths = filt_paths[filt_paths['date'] == selected_date]

if selected_match_id is not None:
    filt_events = filt_events[filt_events['match_id'] == selected_match_id]
    filt_paths = filt_paths[filt_paths['match_id'] == selected_match_id]
elif multi_player_only:
    # When showing "all matches" but filtered to multi-player only,
    # restrict to the multi-player match_ids
    valid_match_ids = filtered_matches['match_id'].tolist()
    filt_events = filt_events[filt_events['match_id'].isin(valid_match_ids)]
    filt_paths = filt_paths[filt_paths['match_id'].isin(valid_match_ids)]


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


# ---------- Build the visualization ----------

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

filt_events = add_pixels(filt_events)
filt_paths = add_pixels(filt_paths)

EVENT_STYLES = {
    'Loot':          {'color': '#FFD700', 'symbol': 'square',      'size': 6,  'name': 'Loot',        'show_var': 'show_loot'},
    'Kill':          {'color': '#FF1744', 'symbol': 'x',           'size': 16, 'name': 'Human kill',  'show_var': 'show_kills'},
    'Killed':        {'color': '#FF1744', 'symbol': 'circle',      'size': 12, 'name': 'Human killed','show_var': 'show_killed'},
    'BotKill':       {'color': '#FF9800', 'symbol': 'x',           'size': 10, 'name': 'Bot kill',    'show_var': 'show_bot_kills'},
    'BotKilled':     {'color': '#E040FB', 'symbol': 'circle',      'size': 10, 'name': 'Killed by bot','show_var': 'show_bot_killed'},
    'KilledByStorm': {'color': '#9C27B0', 'symbol': 'triangle-up', 'size': 14, 'name': 'Storm death', 'show_var': 'show_storm'},
}

# Map layer toggles (variable name → boolean)
LAYER_FLAGS = {
    'show_loot': show_loot,
    'show_kills': show_kills,
    'show_killed': show_killed,
    'show_bot_kills': show_bot_kills,
    'show_bot_killed': show_bot_killed,
    'show_storm': show_storm,
}


fig = go.Figure()

# Background image
fig.add_layout_image(
    dict(
        source=minimap, xref="x", yref="y",
        x=0, y=0, sizex=img_w, sizey=img_h,
        sizing="stretch", layer="below",
    )
)

# ---------- Decide rendering mode based on player count ----------
n_humans_visible = filt_paths[filt_paths['is_human']]['user_id'].nunique() if len(filt_paths) else 0
single_match_mode = (selected_match_id is not None) or n_humans_visible <= 8

# A high-contrast palette for distinguishing individual players
PLAYER_PALETTE = [
    '#00E5FF', '#FFEA00', '#76FF03', '#F50057', '#651FFF',
    '#FF6E40', '#1DE9B6', '#FF4081', '#7C4DFF', '#FFAB00',
    '#69F0AE', '#E040FB', '#40C4FF', '#FF8A65', '#B2FF59',
    '#FFD740', '#536DFE', '#FF80AB', '#84FFFF', '#EEFF41',
    '#FF5252', '#A7FFEB', '#B388FF', '#FFAB91',
]


def _connect_per_user(df: pd.DataFrame, col: str) -> list:
    """Returns flat list with None breaks between different user_ids (for line breaks in Plotly)."""
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


# ---------- Build the figure ----------
fig = go.Figure()

# Background image
fig.add_layout_image(
    dict(
        source=minimap, xref="x", yref="y",
        x=0, y=0, sizex=img_w, sizey=img_h,
        sizing="stretch", layer="below",
    )
)

human_paths_df = filt_paths[filt_paths['is_human']].sort_values(['user_id', 'ts_ms'])
bot_paths_df   = filt_paths[~filt_paths['is_human']].sort_values(['user_id', 'ts_ms'])

# ---------- Bot paths ----------
# In single-match mode: bots get visible (but muted) per-bot colors with markers.
# In multi-match mode: bots stay as faint grouped gray lines (too many to color individually).
if show_bot_paths and len(bot_paths_df) > 0:
    if single_match_mode:
        # Muted palette for bots — visible but doesn't compete with humans
        BOT_PALETTE = [
            '#FFA726', '#A1887F', '#90A4AE', '#BCAAA4',
            '#9E9D24', '#8D6E63', '#78909C', '#6D4C41',
            '#827717', '#5D4037', '#455A64', '#4E342E',
            '#33691E', '#3E2723', '#263238', '#1B5E20',
        ]
        unique_bots = sorted(bot_paths_df['user_id'].unique().tolist())
        bot_colors = {bid: BOT_PALETTE[i % len(BOT_PALETTE)] for i, bid in enumerate(unique_bots)}

        for bid in unique_bots:
            bdf = bot_paths_df[bot_paths_df['user_id'] == bid]
            if len(bdf) == 0:
                continue
            fig.add_trace(go.Scatter(
                x=bdf['px'], y=bdf['py'],
                mode='lines+markers',
                line=dict(color=bot_colors[bid], width=2, dash='dot'),  # dotted to distinguish from humans
                marker=dict(
                    size=8,
                    color=bot_colors[bid],
                    opacity=0.7,
                    line=dict(width=1, color='black'),
                ),
                opacity=0.6,
                name=f"Bot-{bid}",
                hovertemplate=f"<b>Bot {bid}</b><br>Position<extra></extra>",
            ))
    else:
        # Multi-match mode: keep them subtle
        fig.add_trace(go.Scatter(
            x=_connect_per_user(bot_paths_df, 'px'),
            y=_connect_per_user(bot_paths_df, 'py'),
            mode='lines',
            line=dict(color='gray', width=1),
            opacity=0.15,
            name=f"Bot paths ({bot_paths_df['user_id'].nunique()} bots)",
            hoverinfo='skip',
        ))
# ---------- Event style definitions ----------
EVENT_STYLES = {
    'Loot':          {'symbol': 'diamond',     'size': 14, 'name': 'Loot',         'show_var': 'show_loot'},
    'Kill':          {'symbol': 'x',           'size': 24, 'name': 'Human kill',   'show_var': 'show_kills'},
    'Killed':        {'symbol': 'cross',       'size': 24, 'name': 'Human killed', 'show_var': 'show_killed'},
    'BotKill':       {'symbol': 'x',           'size': 18, 'name': 'Bot kill',     'show_var': 'show_bot_kills'},
    'BotKilled':     {'symbol': 'cross',       'size': 18, 'name': 'Killed by bot','show_var': 'show_bot_killed'},
    'KilledByStorm': {'symbol': 'triangle-up', 'size': 22, 'name': 'Storm death',  'show_var': 'show_storm'},
}

# Default colors for "all matches" mode (event-type-based)
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

if single_match_mode and n_humans_visible > 0:
    # ---------- PER-PLAYER COLORING ----------
    # Each human gets a unique color used for both their path and their events.
    unique_humans = sorted(human_paths_df['user_id'].unique().tolist())
    player_colors = {uid: PLAYER_PALETTE[i % len(PLAYER_PALETTE)] for i, uid in enumerate(unique_humans)}

    # Draw each player as: a path line + clearly-visible position markers.
    # One trace per player so the legend lists them individually.
    for uid in unique_humans:
        if not show_human_paths:
            break
        pdf = human_paths_df[human_paths_df['user_id'] == uid]
        if len(pdf) == 0:
            continue
        # Count this player's events for the legend label
        their_events = filt_events[filt_events['user_id'] == uid]
        n_loot = (their_events['event'] == 'Loot').sum()
        n_kills = ((their_events['event'] == 'Kill') | (their_events['event'] == 'BotKill')).sum()
        died = (their_events['event'].isin(['Killed', 'BotKilled', 'KilledByStorm'])).any()
        death_emoji = " 💀" if died else ""

        # Path line + visible position dots, all in this player's color
        fig.add_trace(go.Scatter(
            x=pdf['px'], y=pdf['py'],
            mode='lines+markers',
            line=dict(color=player_colors[uid], width=2.5),
            marker=dict(
                size=9,
                color=player_colors[uid],
                opacity=0.9,
                line=dict(width=1.5, color='black'),  # black outline so they pop against the map
            ),
            opacity=0.95,
            name=f"P-{uid[:6]} ({n_kills}K {n_loot}L){death_emoji}",
            hovertemplate=f"<b>Player {uid[:8]}</b><br>Position<extra></extra>",
        ))

        # Mark the START of the journey with a green star (very visible)
        if len(pdf) > 0:
            start = pdf.iloc[0]
            fig.add_trace(go.Scatter(
                x=[start['px']], y=[start['py']],
                mode='markers',
                marker=dict(
                    size=18, color=player_colors[uid],
                    symbol='star',
                    line=dict(width=2, color='white'),
                ),
                name=None,
                showlegend=False,
                hovertemplate=f"<b>Start: Player {uid[:8]}</b><extra></extra>",
            ))

    # Draw events colored by player. Bigger sizes + clearer symbol differentiation.
    for event_type, style in EVENT_STYLES.items():
        if not LAYER_FLAGS[style['show_var']]:
            continue
        for uid in unique_humans:
            subset = filt_events[
                (filt_events['event'] == event_type) & (filt_events['user_id'] == uid)
            ]
            if len(subset) == 0:
                continue
            fig.add_trace(go.Scatter(
                x=subset['px'], y=subset['py'],
                mode='markers',
                marker=dict(
                    size=style['size'],
                    color=player_colors[uid],
                    symbol=style['symbol'],
                    line=dict(width=2, color='white'),  # white border so events stand out from path dots
                ),
                name=None,
                showlegend=False,
                hovertemplate=(
                    f"<b>{style['name']}</b><br>"
                    f"Player: {uid[:8]}<br>"
                    "World: (%{customdata[0]:.0f}, %{customdata[1]:.0f})<extra></extra>"
                ),
                customdata=subset[['x', 'z']].values,
            ))

else:
    # ---------- MULTI-MATCH MODE: generic colors ----------
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
        subset = filt_events[filt_events['event'] == event_type]
        if len(subset) == 0:
            continue
        fig.add_trace(go.Scatter(
            x=subset['px'], y=subset['py'],
            mode='markers',
            marker=dict(
                size=style['size'],
                color=DEFAULT_EVENT_COLORS[event_type],
                symbol=style['symbol'],
                line=dict(width=0.5, color='black'),
            ),
            name=f"{style['name']} ({len(subset)})",
            hovertemplate=(
                f"<b>{style['name']}</b><br>"
                "World: (%{customdata[0]:.0f}, %{customdata[1]:.0f})<extra></extra>"
            ),
            customdata=subset[['x', 'z']].values,
        ))

# Layout
fig.update_xaxes(
    range=[0, img_w], showgrid=False, zeroline=False,
    showticklabels=False, visible=False,
)
fig.update_yaxes(
    range=[img_h, 0], scaleanchor="x", scaleratio=1,
    showgrid=False, zeroline=False, showticklabels=False, visible=False,
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

# Show the map (or empty state)
if len(filt_events) == 0 and len(filt_paths) == 0:
    st.info("No events match the current filters. Try widening your selection.")
else:
    st.plotly_chart(fig, use_container_width=True)


# ---------- Stats panel ----------

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
        })