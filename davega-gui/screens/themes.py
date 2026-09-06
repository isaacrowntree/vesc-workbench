"""Themes: palette plus layout name, as data.

Every hex here is the same value used in the mockups
(`davega-gui/mockups/themes.html`), so what you see there is what the device
draws. `test_themes.py` asserts that parity rather than trusting it.

Colours are stored as 24-bit and converted to the panel's RGB565 on load, so
these stay readable and diffable.
"""
from . import palette


def _565(hexstr):
    v = int(hexstr.lstrip("#"), 16)
    return palette.rgb((v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF)


class Theme:
    def __init__(self, key, name, lineage, layout, ground, ink, accent,
                 warn, danger, track, dim=None):
        self.key = key
        self.name = name
        self.lineage = lineage
        self.layout = layout
        self.ground = _565(ground)
        self.ink = _565(ink)
        self.accent = _565(accent)
        self.warn = _565(warn)
        self.danger = _565(danger)
        self.track = _565(track)
        self.dim = _565(dim or track)

    def soc_color(self, pct):
        """Charge colour. Themes with a single accent keep it; themes with a
        warn/danger pair ramp through them."""
        if pct > 0.5:
            return self.accent
        return self.warn if pct > 0.2 else self.danger

    def temp_color(self, t, start):
        return self.danger if t >= start else self.ink

    def __repr__(self):
        return "<Theme %s/%s>" % (self.key, self.layout)


THEMES = {t.key: t for t in (
    # The default: best idea from each of the others, nothing else.
    Theme("nazare", "Nazare", "the board", "flagship",
          ground="#06080B", ink="#EDF1F7", accent="#3DDCFF",
          warn="#FFB020", danger="#FF4D4D", track="#1A2029", dim="#5C6878"),

    Theme("rosso", "Rosso", "Maranello", "dial",
          ground="#0A0000", ink="#F5F0E6", accent="#FFD100",
          warn="#D40000", danger="#D40000", track="#3A0000", dim="#8A6A00"),

    Theme("toro", "Toro", "Sant'Agata", "shards",
          ground="#0C0F0A", ink="#E8FFD0", accent="#A8FF00",
          warn="#A8FF00", danger="#FF3B00", track="#1A2110", dim="#465C22"),

    Theme("papaya", "Papaya", "Woking", "hairline",
          ground="#050505", ink="#FFFFFF", accent="#FF7A00",
          warn="#FF7A00", danger="#FF2D2D", track="#1B1B1B", dim="#6E6E6E"),

    Theme("ghost", "Ghost", "Angelholm", "bare",
          ground="#000000", ink="#F7F5F0", accent="#C9A227",
          warn="#C9A227", danger="#B03030", track="#2A2A28", dim="#8B8880"),

    Theme("nevera", "Nevera", "Sveta Nedelja", "flow",
          ground="#04080C", ink="#DCE9F2", accent="#00E5C0",
          warn="#0A5FFF", danger="#FF5470", track="#123040", dim="#4E7285"),

    Theme("hybrid", "Hybrid", "Toyota City", "eco",
          ground="#0E1418", ink="#EAF2F4", accent="#5BC8AF",
          warn="#2F6E8F", danger="#E06C5A", track="#233038", dim="#5F7C88"),

    Theme("minimal", "Minimal", "Palo Alto", "bare",
          ground="#101012", ink="#FFFFFF", accent="#FFFFFF",
          warn="#8A8A90", danger="#E23C3C", track="#3A3A3E", dim="#8A8A90"),

    Theme("motorsport", "Motorsport", "Munich", "rail",
          ground="#0A0C10", ink="#E9EDF2", accent="#0C63C4",
          warn="#E9EDF2", danger="#7A1E2E", track="#1B2028", dim="#5C6675"),

    Theme("silver", "Silver", "Affalterbach", "rings",
          ground="#0F1113", ink="#C8CDD4", accent="#C8CDD4",
          warn="#8E959F", danger="#C4141E", track="#22262B", dim="#8E959F"),
)}

DEFAULT = "nazare"


def get(key):
    return THEMES.get(key or DEFAULT, THEMES[DEFAULT])
