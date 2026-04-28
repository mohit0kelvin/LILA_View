# 🎮 LILA BLACK — Player Journey Visualizer

A web-based visualization tool for exploring player behavior in **LILA BLACK**, an extraction shooter game. Built for the Level Design team to understand how players actually navigate maps — where fights break out, which areas get ignored, and how matches unfold.

## 🔗 Live App

**[lilaview.streamlit.app](https://lilaview.streamlit.app)**

> No login required. Open the link, pick a map and a match, and start exploring.

---

## What It Does

The tool turns 1,243 raw telemetry files into an interactive level-designer-friendly view of the game. From the live URL, you can:

- **Browse 796 matches** across 3 maps (AmbroseValley, GrandRift, Lockdown) and 5 days of production data
- **Watch a match unfold** with a timeline scrubber + play/pause controls
- **See per-player journeys** — each player gets a unique color, with their path, kills, loot pickups, and deaths colored to match
- **Filter** by map, date, multi-player matches only, and individual event types
- **View heatmaps** of kill zones, death zones, or high-traffic areas across the dataset
- **Switch between two heatmap styles**: clean glow-point overlays or traditional density grids

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.13 |
| Web framework | [Streamlit](https://streamlit.io) |
| Charting | [Plotly](https://plotly.com/python/) |
| Data processing | pandas + pyarrow |
| Image handling | Pillow |
| Hosting | [Streamlit Community Cloud](https://share.streamlit.io) |

For the rationale behind these choices, see [`ARCHITECTURE.md`](./ARCHITECTURE.md).

## Repository Structure

```
.
├── app.py                  # Main Streamlit app — all UI and visualization logic
├── prepare_data.py         # One-time data prep pipeline (raw parquet → clean files)
├── utils.py                # Coordinate transform + map config
├── requirements.txt        # Python dependencies
├── ARCHITECTURE.md         # Architecture decisions and tradeoffs
├── INSIGHTS.md             # 3 findings from using the tool
├── data/
│   └── processed/          # Pre-computed clean files used by the app
│       ├── events.parquet
│       ├── paths.parquet
│       └── matches.parquet
└── minimaps/               # Top-down PNG/JPG of each map
    ├── AmbroseValley_Minimap.png
    ├── GrandRift_Minimap.png
    └── Lockdown_Minimap.jpg
```

> **Note:** The raw 1,243 parquet files (`data/raw/`) are not included in this repo — they're regenerated/reprocessed by `prepare_data.py` from the original dataset.

## Run Locally

You'll need Python 3.10+ installed. The data preprocessing step requires the original `player_data.zip` extracted into `data/raw/`.

```bash
# 1. Clone the repo
git clone https://github.com/mohit0kelvin/LILA_View.git
cd LILA_View

# 2. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\activate   # Windows
# OR: source venv/bin/activate    # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. (One-time) Run the data prep pipeline if data/processed/ is empty
#    Requires raw data extracted into data/raw/{February_10..14}/
python prepare_data.py

# 5. Launch the app
streamlit run app.py
```

Then open the URL Streamlit prints (usually `http://localhost:8501`).

## No Environment Variables Needed

This project doesn't require any API keys, secrets, or environment variables. All data is local.

## Documentation

- 📐 **[ARCHITECTURE.md](./ARCHITECTURE.md)** — How the system is built, why we made the choices we did, and what assumptions we had to make about the data
- 💡 **[INSIGHTS.md](./INSIGHTS.md)** — Three things we learned about LILA BLACK by using the tool we built

## Built For

LILA Games' Associate Product Manager written test — Player Journey Visualization Tool assignment.