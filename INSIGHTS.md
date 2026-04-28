# Insights

Three findings discovered by using the visualization tool to explore LILA BLACK's production telemetry. Each follows the structure requested in the brief: what was observed, supporting evidence, what's actionable, and why a level designer should care.

All numbers below are computed directly from the processed dataset (`data/processed/`) and verified against the raw data.

---

## Insight 1: Storm Deaths Are an Exclusive Symptom of Disengaged Play

### What caught my eye

While testing the playback feature, I tried to find a match where a player died to the storm — and could not. The "Killed by Storm" event marker (purple triangle) was completely absent from every multi-player match. This was unexpected: in any battle royale or extraction shooter, the storm is a primary threat designed to drive movement and create endgame tension.

A diagnostic pass on the data confirmed the observation. Of the 796 matches in the dataset, **all 39 storm deaths occur in single-file matches** — sessions with one human and minimal or no other participants. **No match with 5 or more participant files contains a single storm death.**

### Supporting evidence

| Cohort | Match count | Storm deaths |
|---|---|---|
| Single-file matches (likely solo, test, or disengaged) | 743 | **39** |
| Multi-player matches (5+ files) | 53 | **0** |

The pattern is absolute: every storm death in the entire dataset comes from a player who was alone. Engaged players in real multi-player matches never die to the storm.

### Actionable interpretation

The storm is a core design element intended to drive movement and create endgame pressure, but it is functionally invisible to engaged players. Three explanations are possible, each with different implications:

1. **Storm timing is too forgiving.** If no engaged player is ever caught by it, the storm timer may need to tighten, or the play zone may need to shrink earlier in the match.
2. **The storm is succeeding by deterring rather than killing.** Players never die because they always extract in time. In this reading, the absence of deaths is a design success — but it should be measured directly via storm-pressure proximity rather than inferred from absent deaths.
3. **Telemetry coverage may be limited to early-match phases.** If telemetry sampling does not extend into the late-game extraction window, storm deaths in real matches would be undercounted.

**Metrics that would shift if this were addressed:** average match duration, extraction completion rate, frequency of `KilledByStorm` events in multi-player matches (currently zero), and average distance between players and the storm boundary in late-game samples.

### Why a level designer should care

The storm is the primary tool for shaping endgame geography on every map — it dictates which choke points come into play, which extraction routes are viable, and where the final fights happen. If engaged players never experience storm pressure, large portions of the late-game map design are not being experienced as intended. Validating storm parameters or running targeted player-experience studies should be a priority.

---

## Insight 2: Most Human Matches End in Death, Not Extraction

### What caught my eye

While building the per-match stats panel, the death markers consistently outnumbered extraction-style "loot-and-leave" patterns. A direct count revealed the scale of the problem: **out of 778 matches with at least one human player, 441 end with the human dying — that's 56.7%.**

For a game whose central design loop is *extracting alive with loot*, fewer than half of all human sessions reach that goal.

### Supporting evidence

| Outcome | Count | Percentage |
|---|---|---|
| Match ended with human death (Killed, BotKilled, or KilledByStorm) | **441** | **56.7%** |
| Match ended without recorded human death (extracted, disconnected, or session ended) | 337 | 43.3% |
| **Total matches involving at least one human** | **778** | 100% |

> *Note on precision: "extracted" here means "no death event recorded for the human in this match." This category technically includes disconnects, AFK sessions, and partial-data matches. The death rate is therefore a confident floor; the true success rate is probably lower than 43%.*

### Actionable interpretation

A 56.7% death rate is a structural product signal. There are several possible drivers, each addressable through level design:

1. **Bot density may be too high.** Combined `BotKilled` events (700 humans killed by bots) and `BotKill` events (2,415 bots killed by humans) suggest a strong PvE component, but the 700 bot-on-human kills represent a large share of the death rate. Reducing bot density in extraction approaches, or repositioning bots away from extraction routes, would increase extraction success.
2. **Extraction zones may be too far from typical loot locations.** Looking at the heatmap: the loot-density and combat-density centers don't always align with predictable extraction paths. Adding more accessible extraction options or providing visual cues toward them earlier in the match could help.
3. **Time pressure may peak too sharply.** If the storm or match timer compresses the extraction window aggressively, casual players may not have learned the routes. Telemetry on time-to-death after first loot pickup could clarify this.

**Metrics that would shift:** extraction rate, average distance traveled before death, average loot picked up before death, player retention (extraction success is a known correlate of return rate).

### Why a level designer should care

Extraction routes are level design. Where the safe paths are, how visible they are, what bots and obstacles exist along them — these are direct level-design decisions. A 43% extraction success rate suggests the routes are either too contested, too unclear, or both. Per-map extraction rates (computable from this data) would identify which maps under-perform and let designers compare layouts. The visualization tool's heatmap and per-match views are the natural feedback loop for this work.

---

## Insight 3: Each Map Has 2–3 Activity Hotspots; the Rest Is Functionally Dead Content

### What caught my eye

The traffic heatmap on AmbroseValley shows extreme spatial concentration: a dense glow around the central building complex near the river, a secondary cluster around the southern industrial buildings, and a smaller hotspot near the western Mining Compound. Outside these zones, large portions of the map have almost no movement events at all. The pattern repeats on the other two maps.

GrandRift offers a particularly clean validation. The map's official minimap labels the "Mine Pit" as the contested zone (highlighted in red). The data confirms it — Mine Pit dominates GrandRift's combat heatmap. Designer intent matches player behavior on that one zone.

### Supporting evidence

Combat and loot events per map (events.parquet only):

| Map | Events | Share of activity |
|---|---|---|
| AmbroseValley | 12,242 events (9,955 loot + 2,287 combat) | **70.5%** of all activity |
| Lockdown | 2,644 events (2,050 loot + 594 combat) | 21.9% |
| GrandRift | 1,120 events (880 loot + 240 combat) | 7.5% |

Two patterns stand out:

1. **AmbroseValley accounts for 70%+ of all dataset activity.** The map is roughly 9× more active than GrandRift.
2. **Within each map, activity concentrates in 2–3 zones**, leaving the majority of playable area as low-traffic dead content. This is visible in the traffic heatmap on every map.

The loot-to-combat ratio is also remarkably consistent across maps — between 3.5× and 4.4× more loot events than combat events on every map. Players consistently loot far more than they fight, regardless of which map they're on.

### Actionable interpretation

The strong concentration of activity points to two distinct opportunities:

1. **Dead zones need stronger pull.** Large portions of every map see almost no traffic. Adding meaningful loot, objectives, or extraction points in these underused regions would distribute player movement and effectively expand the playable map. The traffic heatmap is the direct measurement tool for whether such interventions work.
2. **Hot zones may benefit from rebalancing.** When a single zone (such as AmbroseValley's central complex) absorbs the majority of an entire map's combat, that zone is functionally a deathmatch arena rather than one location among many. Splitting high-value loot across more zones or adjusting risk/reward at the contested center would force players to make routing decisions instead of converging on one spot.

**Metrics that would shift:** map area utilization (% of map cells with activity above some threshold), event entropy across the map, average distance from hotspot centroids, and ideally the death rate at the contested center (currently a single hotspot on AmbroseValley dominates kill events).

### Why a level designer should care

This finding has the most direct level-design implication of the three. Every minute spent designing a region players never visit is wasted effort, and every encounter that happens at the same one or two zones means the rest of the map is effectively decorative. Before-and-after heatmap comparisons would tell a designer in seconds whether a layout change is doing what they intended — and the tool already produces those views with two clicks. Of the three insights in this document, this one comes with the most immediate and concrete iteration loop.