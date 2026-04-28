"""
Phase 2: Data preparation pipeline.

Reads all raw parquet files from data/raw/, processes them, and produces
3 clean files in data/processed/:
  - events.parquet:  combat & loot events only
  - paths.parquet:   position events, downsampled
  - matches.parquet: one row per match with summary stats

Run this once locally:  python prepare_data.py
"""

import pandas as pd
import os
import re
import time

# ---------- Configuration ----------

RAW_DIR = "data/raw"
PROCESSED_DIR = "data/processed"
DAY_FOLDERS = ["February_10", "February_11", "February_12", "February_13", "February_14"]

DATE_MAP = {
    "February_10": "2026-02-10",
    "February_11": "2026-02-11",
    "February_12": "2026-02-12",
    "February_13": "2026-02-13",
    "February_14": "2026-02-14",  # partial day
}

POSITION_DOWNSAMPLE_RATE = 3
COMBAT_EVENTS = {"Kill", "Killed", "BotKill", "BotKilled", "Loot", "KilledByStorm"}
POSITION_EVENTS = {"Position", "BotPosition"}

UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')


def is_human_user(user_id: str) -> bool:
    """Returns True for UUIDs (humans), False for numeric IDs (bots)."""
    return bool(UUID_PATTERN.match(user_id))


def load_all_raw() -> pd.DataFrame:
    """Read every parquet file in every day folder, return combined DataFrame."""
    print("Loading all raw parquet files...")
    start = time.time()

    all_dfs = []
    for day in DAY_FOLDERS:
        folder = os.path.join(RAW_DIR, day)
        files = os.listdir(folder)
        print(f"  {day}: {len(files)} files")
        for filename in files:
            df = pd.read_parquet(os.path.join(folder, filename))
            df['date'] = DATE_MAP[day]
            df['source_file'] = filename
            all_dfs.append(df)

    combined = pd.concat(all_dfs, ignore_index=True)
    elapsed = time.time() - start
    print(f"  Done. {len(combined):,} total rows loaded in {elapsed:.1f}s\n")
    return combined


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Decode event bytes, add is_human, compute ts_ms and ts_relative."""
    print("Cleaning data...")
    start = time.time()

    df['event'] = df['event'].apply(lambda x: x.decode('utf-8') if isinstance(x, bytes) else x)
    df['is_human'] = df['user_id'].apply(is_human_user)

    # Per the README: ts is "milliseconds elapsed within the match, not wall-clock time".
    # The raw int64 representation of datetime64[ms] gives us the underlying millisecond value.
    df['ts_ms'] = df['ts'].astype('int64')

    # Relative timestamp within each match (0 = match start)
    match_starts = df.groupby('match_id')['ts_ms'].transform('min')
    df['ts_relative'] = df['ts_ms'] - match_starts

    elapsed = time.time() - start
    print(f"  Done in {elapsed:.1f}s")
    print(f"  Unique events: {df['event'].nunique()}")
    print(f"  Humans: {df[df['is_human']]['user_id'].nunique()}, "
          f"Bots: {df[~df['is_human']]['user_id'].nunique()}\n")
    return df


def split_outputs(df: pd.DataFrame):
    """Produce 3 separate DataFrames from the cleaned data."""
    print("Splitting into output files...")

    # --- events.parquet: combat & loot only ---
    events_df = df[df['event'].isin(COMBAT_EVENTS)].copy()
    events_df = events_df[[
        'match_id', 'map_id', 'date', 'user_id', 'is_human',
        'event', 'x', 'z', 'ts_ms', 'ts_relative'
    ]].reset_index(drop=True)
    print(f"  events:  {len(events_df):,} rows")

    # --- paths.parquet: position events, downsampled ---
    positions_df = df[df['event'].isin(POSITION_EVENTS)].copy()
    positions_df = positions_df.sort_values(['match_id', 'user_id', 'ts_ms'])
    positions_df['_within_group_idx'] = positions_df.groupby(['match_id', 'user_id']).cumcount()
    positions_df = positions_df[positions_df['_within_group_idx'] % POSITION_DOWNSAMPLE_RATE == 0]
    paths_df = positions_df[[
        'match_id', 'map_id', 'date', 'user_id', 'is_human',
        'event', 'x', 'z', 'ts_ms', 'ts_relative'
    ]].reset_index(drop=True)
    print(f"  paths:   {len(paths_df):,} rows (downsampled by {POSITION_DOWNSAMPLE_RATE}x)")

    # --- matches.parquet: one row per match with summary stats ---
    print(f"  matches: computing per-match summaries...")
    match_summaries = []
    for match_id, mdf in df.groupby('match_id'):
        humans = mdf[mdf['is_human']]['user_id'].unique()
        bots = mdf[~mdf['is_human']]['user_id'].unique()
        event_counts = mdf['event'].value_counts().to_dict()
        duration_ms = int(mdf['ts_relative'].max())

        match_summaries.append({
            'match_id':       match_id,
            'map_id':         mdf['map_id'].iloc[0],
            'date':           mdf['date'].iloc[0],
            'n_files':        mdf['source_file'].nunique(),
            'n_humans':       len(humans),
            'n_bots':         len(bots),
            'n_events_total': len(mdf),
            'n_kills':        event_counts.get('Kill', 0),
            'n_killed':       event_counts.get('Killed', 0),
            'n_bot_kills':    event_counts.get('BotKill', 0),
            'n_bot_killed':   event_counts.get('BotKilled', 0),
            'n_storm_deaths': event_counts.get('KilledByStorm', 0),
            'n_loot':         event_counts.get('Loot', 0),
            'duration_ms':    duration_ms,
            'has_playback':   duration_ms > 0,
        })

    matches_df = pd.DataFrame(match_summaries)
    matches_df = matches_df.sort_values(
        ['date', 'map_id', 'n_files'], ascending=[True, True, False]
    ).reset_index(drop=True)
    print(f"  matches: {len(matches_df):,} rows")
    print(f"           {matches_df['has_playback'].sum()} have playback (non-zero duration)")

    return events_df, paths_df, matches_df


def save_outputs(events_df, paths_df, matches_df):
    """Write the three parquet files to data/processed/."""
    print(f"\nSaving outputs to {PROCESSED_DIR}/")
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    events_path = os.path.join(PROCESSED_DIR, "events.parquet")
    paths_path = os.path.join(PROCESSED_DIR, "paths.parquet")
    matches_path = os.path.join(PROCESSED_DIR, "matches.parquet")

    events_df.to_parquet(events_path, index=False)
    paths_df.to_parquet(paths_path, index=False)
    matches_df.to_parquet(matches_path, index=False)

    for path in [events_path, paths_path, matches_path]:
        size_kb = os.path.getsize(path) / 1024
        print(f"  {path}: {size_kb:.1f} KB")


if __name__ == "__main__":
    print("=" * 60)
    print("LILA BLACK Data Preparation Pipeline")
    print("=" * 60 + "\n")

    raw = load_all_raw()
    cleaned = clean_data(raw)
    events_df, paths_df, matches_df = split_outputs(cleaned)
    save_outputs(events_df, paths_df, matches_df)

    print("\n✅ Done!")
    print(f"\nQuick stats:")
    print(f"  Events file:  {len(events_df):,} rows")
    print(f"  Paths file:   {len(paths_df):,} rows")
    print(f"  Matches file: {len(matches_df):,} matches")
    print(f"  Playable matches: {matches_df['has_playback'].sum()}")