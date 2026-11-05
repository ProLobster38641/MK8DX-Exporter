"""MK8DX KCL collision flags. Attribute = type (bits 0-4) + variant * 0x20 (bits 5-7) + special flags (bits 12-15).
Sources: mk8.tockdom.com/wiki/KCL_flag, Track Studio docs, KclLibrary MK8DX preset."""

TYPES = [  # (id, name, description, variant names)
    (0x00, "Road 1", "Normal road", ["Asphalt", "Concrete", "Stone", "Wood", "Metal plate", "Metal grate", "Carpet", "Unknown"]),
    (0x01, "Road 2", "Normal road", ["Grass (small effects)", "Dirt (small effects)", "Glass", "Grass", "Piano", "Metallophone", "Bone", "Unknown"]),
    (0x02, "Road 3", "Normal road", ["Bumpy", "Cloth", "Carpet", "Candy", "Sponge", "Carpet 2", "Cloud", "Unknown"]),
    (0x03, "Road 4", "Normal road", ["Tech road", "Unknown", "Unknown", "Wood board", "Ocean floor", "Unknown", "Rainbow Road", "Rainbow Road (glass)"]),
    (0x04, "Sand", "Off-road: slow", []),
    (0x05, "Weak off-road", "Off-road: slower", []),
    (0x06, "Off-road 1", "Off-road", []),
    (0x07, "Off-road 2", "Off-road", ["Chocolate", "Cream", "Cream 2", "Swarovski", "Stone", "Rubber", "Unknown", "Unknown"]),
    (0x08, "Heavy off-road", "Off-road: slowest", ["Sand", "Dirt", "Snow", "None", "Grass", "None", "None", "None"]),
    (0x09, "Slippery", "Slippery road", ["Ice", "Glass", "Water", "Wet asphalt", "None", "None", "None", "None"]),
    (0x0A, "Dash (boost)", "Boost / dash panel", []),
    (0x0B, "Anti-gravity panel", "Gravity panel sounds/effects", []),
    (0x0C, "Glider panel", "Glider ramp panel sounds/effects", []),
    (0x0D, "Pull", "Current (rivers); needs pull paths", ["Water", "River"]),
    (0x0E, "Moving terrain", "Stairs etc.", ["Stairs", "Stairs 2"]),
    (0x0F, "Item road", "Only items collide", []),
    (0x10, "Lakitu rescue", "Lakitu picks you up", []),
    (0x11, "Wall 1", "Solid wall", ["Concrete", "Cliff", "Metal", "Wood", "Ice", "Snow", "Ivy", "Rainbow"]),
    (0x12, "Wall 2", "Solid wall", ["Chocolate", "Musical", "Techno fence", "Glass", "Candy", "Sponge", "Paper", "Cookie"]),
    (0x13, "Wall 3", "Solid wall", ["Leaf", "Car"]),
    (0x14, "LWALL", "Wall (special)", ["Concrete", "Metal", "Bone", "None", "Cloth", "Cloth 2", "Rainbow wall", "None"]),
    (0x15, "Item wall", "Only items collide", []),
    (0x16, "BWALL", "Bouncy wall", ["Cream", "Bush", "Plastic", "Leaf", "Ocean", "Tire", "Cloth", "Cloud"]),
    (0x17, "Invisible wall", "No sound/particles. For out-of-bounds", []),
    (0x18, "Dummy 1", "Unsolid", []),
    (0x19, "Cannon (unused)", "", []),
    (0x1A, "Effect trigger", "", []),
    (0x1B, "Sound trigger", "", []),
    (0x1C, "Fall out (death)", "Respawn: void/water/lava", ["Void", "Water", "Lava", "Lava 2", "Water (desert)", "None", "None", "None"]),
    (0x1D, "Dummy 2", "Unsolid", []),
    (0x1E, "Dummy 3", "Unsolid", []),
    (0x1F, "Zone", "Glider activator (plane above a glider ramp) / flowers", ["Glider activator", "Mud particles", "Orange flowers", "White flowers (slow)", "White flowers", "Green flowers", "None", "None"]),
]
TYPE_BY_ID = {t[0]: t for t in TYPES}

FLAGS = [(0x1000, "Trickable"), (0x2000, "Trickable (extra)"), (0x4000, "High gravity"), (0x8000, "High gravity 2 (stairs)")]

# Quick presets: (key, label, hex)
PRESETS = [
    ("ROAD", "Road (asphalt)", 0x0000), ("ROAD_STONE", "Road (stone)", 0x0040), ("ROAD_WOOD", "Road (wood)", 0x0060),
    ("ROAD_METAL", "Road (metal)", 0x0080), ("GRASS_LIGHT", "Grass road (light)", 0x0061),
    ("SAND", "Sand", 0x0004), ("OFFROAD_W", "Weak off-road", 0x0005), ("OFFROAD", "Off-road", 0x0006),
    ("DIRT_HEAVY", "Dirt (heavy off-road)", 0x0028), ("GRASS", "Grass (heavy off-road)", 0x0088), ("SNOW", "Snow (heavy off-road)", 0x0048),
    ("ICE", "Ice (slippery)", 0x0009), ("WATER_SHALLOW", "Shallow water (slippery)", 0x0049),
    ("BOOST", "Boost / dash panel", 0x000A), ("ANTIGRAV", "Anti-gravity panel", 0x000B), ("GLIDER_PANEL", "Glider panel", 0x000C),
    ("GLIDER", "Glider activator (zone)", 0x001F), ("RAMP", "Trick ramp (road + trickable)", 0x1000),
    ("BOOST_RAMP", "Boost + trick ramp", 0x100A), ("WALL", "Wall (concrete)", 0x0011), ("WALL_ROCK", "Wall (cliff/rock)", 0x0031),
    ("WALL_METAL", "Wall (metal)", 0x0051), ("INVIS_WALL", "Invisible wall", 0x0017), ("ITEM_WALL", "Item wall", 0x0015),
    ("FALL", "Fall out (void)", 0x001C), ("WATER", "Fall out (water)", 0x003C), ("LAVA", "Fall out (lava)", 0x005C),
    ("LAKITU", "Lakitu rescue boundary", 0x0010), ("ITEM_ROAD", "Item road", 0x000F),
]


def describe(attr):
    t = TYPE_BY_ID.get(attr & 0x1F)
    v = (attr >> 5) & 7
    s = t[1] if t else f"Type {attr & 0x1F:#x}"
    if t and t[3]:
        s += f" / {t[3][v] if v < len(t[3]) else v}"
    elif v:
        s += f" / variant {v}"
    fl = [n for b, n in FLAGS if attr & b]
    if attr & 0x0F00:
        fl.append(f"unknown bits {attr & 0x0F00:#x}")
    return s + (" + " + ", ".join(fl) if fl else "") + f"  (COL_{attr:X})"


def color(attr):
    """Viewport colour per type (RGB 0-1)."""
    import colorsys
    t = attr & 0x1F
    if t <= 3: base = (0.55, 0.55, 0.6)
    elif t <= 8: base = (0.6, 0.45, 0.2)
    elif t == 9: base = (0.6, 0.9, 1.0)
    elif t in (0x0A, 0x0B, 0x0C): base = (1.0, 0.6, 0.0)
    elif t == 0x1F: base = (0.2, 1.0, 0.3)
    elif 0x11 <= t <= 0x16: base = (0.8, 0.15, 0.15)
    elif t == 0x17: base = (0.9, 0.4, 0.8)
    elif t == 0x1C: base = ((0.1, 0.2, 0.05), (0.1, 0.3, 1.0), (1.0, 0.25, 0.0))[min((attr >> 5) & 7, 2)] if (attr >> 5) & 7 < 3 else (1, .3, 0)
    elif t == 0x10: base = (1.0, 1.0, 0.2)
    else: base = (0.5, 0.2, 0.9)
    h, l, s = colorsys.rgb_to_hls(*base)
    l = min(0.9, max(0.15, l + (((attr >> 5) & 7) - 3) * 0.04))
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    if attr & 0xF000:   # flags: tint brighter
        r, g, b = [min(1, c * 0.7 + 0.3) for c in (r, g, b)]
    return (r, g, b)
