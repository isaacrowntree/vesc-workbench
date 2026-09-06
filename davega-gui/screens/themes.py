"""Themes: palette plus layout name, as data.

The `lineage` field names whose instrument-cluster design language a theme
borrows from. These are homages built from scratch - no logos, no assets, no
affiliation with or endorsement by any of those companies.

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
    Theme("nazare", "Nazare", "the board it rides on", "flagship",
          ground="#06080B", ink="#EDF1F7", accent="#3DDCFF",
          warn="#FFB020", danger="#FF4D4D", track="#1A2029", dim="#76808D"),

    Theme("rosso", "Rosso", "inspired by Ferrari", "dial",
          ground="#0A0000", ink="#F5F0E6", accent="#FFD100",
          warn="#DC3030", danger="#DC3030", track="#3A0000", dim="#987B1E"),

    Theme("toro", "Toro", "inspired by Lamborghini", "shards",
          ground="#0C0F0A", ink="#E8FFD0", accent="#A8FF00",
          warn="#A8FF00", danger="#FF3B00", track="#1A2110", dim="#77885D"),

    Theme("papaya", "Papaya", "inspired by McLaren", "hairline",
          ground="#050505", ink="#FFFFFF", accent="#FF7A00",
          warn="#FF7A00", danger="#FF2D2D", track="#1B1B1B", dim="#808080"),

    Theme("ghost", "Ghost", "inspired by Koenigsegg", "bare",
          ground="#000000", ink="#F7F5F0", accent="#C9A227",
          warn="#C9A227", danger="#BE5555", track="#2A2A28", dim="#8B8880"),

    Theme("nevera", "Nevera", "inspired by Rimac", "flow",
          ground="#04080C", ink="#DCE9F2", accent="#00E5C0",
          warn="#206DFF", danger="#FF5470", track="#123040", dim="#658494"),

    Theme("hybrid", "Hybrid", "inspired by Toyota", "eco",
          ground="#0E1418", ink="#EAF2F4", accent="#5BC8AF",
          warn="#5085A0", danger="#E06C5A", track="#233038", dim="#6F8993"),

    Theme("minimal", "Minimal", "inspired by Tesla", "bare",
          ground="#101012", ink="#FFFFFF", accent="#FFFFFF",
          warn="#8A8A90", danger="#E23C3C", track="#3A3A3E", dim="#8A8A90"),

    Theme("motorsport", "Motorsport", "inspired by BMW M", "rail",
          ground="#0A0C10", ink="#E9EDF2", accent="#4185D0",
          warn="#E9EDF2", danger="#A56872", track="#1B2028", dim="#79818D"),

    Theme("silver", "Silver", "inspired by Mercedes-AMG", "rings",
          ground="#0F1113", ink="#C8CDD4", accent="#C8CDD4",
          warn="#8E959F", danger="#D24C54", track="#22262B", dim="#8E959F"),
)}

DEFAULT = "nazare"


def get(key):
    return THEMES.get(key or DEFAULT, THEMES[DEFAULT])
