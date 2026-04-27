"""
Utility functions for LILA BLACK Player Journey Visualizer.

The most important function here is `world_to_pixel`, which converts
in-game world coordinates (x, z) to pixel coordinates on the minimap image.
This is the heart of the visualization — get this wrong and nothing maps right.
"""

from PIL import Image

# Map configuration as documented in the data README.
# scale and origin determine the world->minimap-UV transform.
MAP_CONFIGS = {
    "AmbroseValley": {"scale": 900,  "origin_x": -370, "origin_z": -473},
    "GrandRift":     {"scale": 581,  "origin_x": -290, "origin_z": -290},
    "Lockdown":      {"scale": 1000, "origin_x": -500, "origin_z": -500},
}

# Path to each map's minimap image. We read actual image dimensions at runtime
# (instead of trusting the README's stated 1024x1024) because the real images
# are larger and vary per map.
MINIMAP_PATHS = {
    "AmbroseValley": "data/raw/minimaps/AmbroseValley_Minimap.png",
    "GrandRift":     "data/raw/minimaps/GrandRift_Minimap.png",
    "Lockdown":      "data/raw/minimaps/Lockdown_Minimap.jpg",
}


def get_minimap_size(map_id: str) -> tuple[int, int]:
    """Returns (width, height) in pixels of the minimap image for this map."""
    img = Image.open(MINIMAP_PATHS[map_id])
    return img.size  # PIL returns (width, height)


def world_to_pixel(x: float, z: float, map_id: str,
                   img_w: int, img_h: int) -> tuple[float, float]:
    """
    Convert in-game world coordinates (x, z) to pixel coordinates on the minimap.

    Step 1 — world to UV (0..1):
        u = (x - origin_x) / scale
        v = (z - origin_z) / scale

    Step 2 — UV to pixel coords:
        pixel_x = u * img_w
        pixel_y = (1 - v) * img_h     ← Y flipped (image origin is top-left)

    Note: We use only x and z. The y column in the data is elevation (3D height),
    not a 2D map coordinate.
    """
    cfg = MAP_CONFIGS[map_id]
    u = (x - cfg["origin_x"]) / cfg["scale"]
    v = (z - cfg["origin_z"]) / cfg["scale"]
    pixel_x = u * img_w
    pixel_y = (1 - v) * img_h
    return pixel_x, pixel_y


# ---------- Self-test (run this file directly to verify) ----------

if __name__ == "__main__":
    # README example: AmbroseValley, world=(-301.45, -355.55), expected pixels ≈ (78, 890)
    # The README assumes a 1024x1024 image; our actual image is 4320x4320.
    # We test against the actual image dimensions.

    print("Running coordinate transform unit tests...\n")

    # Test 1: README example, scaled to actual image dimensions
    img_w, img_h = get_minimap_size("AmbroseValley")
    px, py = world_to_pixel(-301.45, -355.55, "AmbroseValley", img_w, img_h)
    expected_px = 0.0762 * img_w   # README's UV math says u ≈ 0.0762
    expected_py = (1 - 0.1305) * img_h
    assert abs(px - expected_px) < 1, f"FAIL: px={px}, expected≈{expected_px}"
    assert abs(py - expected_py) < 1, f"FAIL: py={py}, expected≈{expected_py}"
    print(f"  ✅ AmbroseValley README example: ({px:.1f}, {py:.1f})")

    # Test 2: A point at the origin should map to the bottom-left corner of the image
    px, py = world_to_pixel(-370, -473, "AmbroseValley", img_w, img_h)
    assert abs(px - 0) < 1 and abs(py - img_h) < 1, f"Origin failed: ({px}, {py})"
    print(f"  ✅ AmbroseValley origin maps to bottom-left: ({px:.1f}, {py:.1f})")

    # Test 3: A point at origin + scale should map to top-right corner
    px, py = world_to_pixel(-370 + 900, -473 + 900, "AmbroseValley", img_w, img_h)
    assert abs(px - img_w) < 1 and abs(py - 0) < 1, f"Top-right failed: ({px}, {py})"
    print(f"  ✅ AmbroseValley (origin + scale) maps to top-right: ({px:.1f}, {py:.1f})")

    # Test 4: All 3 maps return sensible image sizes
    for map_id in MAP_CONFIGS.keys():
        w, h = get_minimap_size(map_id)
        print(f"  ✅ {map_id} image size: {w} x {h}")

    print("\n✅ All tests passed.")