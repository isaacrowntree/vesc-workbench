"""Themes: palette plus layout name, as data.

The `lineage` field names whose instrument-cluster design language a theme
borrows from. These are homages built from scratch - no logos, no assets, no
affiliation with or endorsement by any of those companies.

Every hex here is the same value used in the mockups
(`davega/mockups/index.html`), so what you see there is what the device
draws. `test_themes.py` asserts that parity rather than trusting it.

Colours are stored as 24-bit and converted to the panel's RGB565 on load, so
these stay readable and diffable.
"""
from . import palette


def _565(hexstr):
    if isinstance(hexstr, int):
        return hexstr
    v = int(hexstr.lstrip("#"), 16)
    return palette.rgb((v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF)


def _to24(c565):
    r, g, b = palette.unpack(c565)
    return (r << 16) | (g << 8) | b


class Theme:
    def __init__(self, key, name, lineage, layout, ground, ink, accent,
                 warn, danger, track, dim=None, light=False):
        self.key = key
        self.name = name
        self.lineage = lineage
        self.layout = layout
        self.light = light
        self._src = (ground, ink, accent, warn, danger, track, dim)
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

    def as_light(self):
        """The daylight variant, derived rather than hand-authored.

        Ground and ink swap roles; every other colour is walked toward black
        until it clears the same contrast bar it had to clear on the dark
        ground. Hue survives, so a theme still looks like itself.
        """
        g, ink, accent, warn, danger, track, dim = self._src
        ground = palette.paper(_565(accent))
        return Theme(
            self.key, self.name, self.lineage, self.layout,
            ground="#%06X" % _to24(ground),
            ink="#%06X" % _to24(palette.darken_until(_565(ink) if False else _565(g),
                                                     ground, palette.MIN_PRIMARY)),
            accent="#%06X" % _to24(palette.darken_until(_565(accent), ground,
                                                        palette.MIN_LABEL)),
            warn="#%06X" % _to24(palette.darken_until(_565(warn), ground,
                                                      palette.MIN_LABEL)),
            # Danger is taken further than the bar requires. On a light
            # ground everything darkens toward the same near-black, and warn
            # and danger converge; giving danger a higher target keeps them
            # apart by construction rather than by luck.
            # Danger is pushed well past the bar. Under deuteranopia amber
            # and red are the same hue, so the only thing left to tell them
            # apart is lightness - and a small gap is not enough.
            danger="#%06X" % _to24(palette.darken_until(
                palette.toward_hue(_565(danger), palette.DANGER_HUE),
                ground, palette.DANGER_LIGHT)),
            track="#%06X" % _to24(palette.mix(ground, _565(g), 0.18)),
            dim="#%06X" % _to24(palette.darken_until(_565(dim or track), ground,
                                                     palette.MIN_LABEL)),
            light=True)

    def __repr__(self):
        return "<Theme %s/%s%s>" % (self.key, self.layout,
                                    " light" if self.light else "")


# Track is the unlit half of a gauge: the empty end of the battery, the far
# side of the flow meter. Too close to the ground and the bar has no visible
# end in sunlight - a third full and a third of a bar floating in space look
# the same. Every track clears MIN_TRACK against its ground, and stays far
# enough below the accent that the lit part still reads as the signal.
THEMES = {t.key: t for t in (
    # The default: best idea from each of the others, nothing else.
    Theme("nazare", "Nazare", "the board it rides on", "flagship",
          ground="#06080B", ink="#EDF1F7", accent="#3DDCFF",
          warn="#FFB020", danger="#FF4D4D", track="#293039", dim="#76808D"),

    Theme("rosso", "Rosso", "inspired by Ferrari", "dial",
          ground="#0A0000", ink="#F5F0E6", accent="#FFD100",
          warn="#FFB43C", danger="#DC3030", track="#4A1818", dim="#987B1E"),

    Theme("toro", "Toro", "inspired by Lamborghini", "shards",
          ground="#0C0F0A", ink="#E8FFD0", accent="#A8FF00",
          warn="#A8FF00", danger="#FF3B00", track="#293018", dim="#77885D"),

    Theme("papaya", "Papaya", "inspired by McLaren", "hairline",
          ground="#050505", ink="#FFFFFF", accent="#FF7A00",
          warn="#FF7A00", danger="#FF6BB0", track="#292C29", dim="#808080"),

    Theme("ghost", "Ghost", "inspired by Koenigsegg", "bare",
          ground="#000000", ink="#F7F5F0", accent="#C9A227",
          warn="#C9A227", danger="#BE5555", track="#2A2A28", dim="#8B8880"),

    Theme("nevera", "Nevera", "inspired by Rimac", "flow",
          ground="#04080C", ink="#DCE9F2", accent="#00E5C0",
          warn="#206DFF", danger="#FF5470", track="#123040", dim="#658494"),

    Theme("hybrid", "Hybrid", "inspired by Toyota", "eco",
          ground="#0E1418", ink="#EAF2F4", accent="#5BC8AF",
          warn="#5085A0", danger="#E06C5A", track="#203439", dim="#6F8993"),

    Theme("minimal", "Minimal", "inspired by Tesla", "minimal",
          ground="#101012", ink="#FFFFFF", accent="#7FC4FF",
          warn="#FFC24D", danger="#FF6B6B", track="#3A3A3E", dim="#8A8A90"),

    Theme("motorsport", "Motorsport", "inspired by BMW M", "rail",
          ground="#0A0C10", ink="#E9EDF2", accent="#4185D0",
          warn="#E9EDF2", danger="#A56872", track="#293039", dim="#79818D"),

    Theme("silver", "Silver", "inspired by Mercedes-AMG", "rings",
          ground="#0F1113", ink="#C8CDD4", accent="#7FAAD8",
          warn="#E0A65C", danger="#D24C54", track="#293031", dim="#8E959F"),
)}

DEFAULT = "nazare"

#: Daylight variants, derived on demand and remembered - but only the one in
#: use. Building all ten at import cost ten Theme objects and the arithmetic
#: behind them on a board with 98 kB of heap, every boot, for a setting most
#: riders never turn on. Keeping all ten that were ever asked for was the same
#: mistake spread over time: cycling the themes in day mode left ten of them
#: resident and ran the board out of memory where night mode survived.
#:
#: A rider looks at one theme. Caching the other nine caches nothing anybody
#: is looking at.
LIGHT = {}


def light_theme(key):
    t = LIGHT.get(key)
    if t is None:
        LIGHT.clear()
        t = LIGHT[key] = THEMES[key].as_light()
    return t


def get(key, light=False):
    """A theme by name.

    `light` picks the daylight variant, and so does a "@light" suffix on the
    key - so a screen can be handed one string and never need to know there
    are two tables.
    """
    if key and key.endswith("@light"):
        key, light = key[:-6], True
    if key not in THEMES:
        key = DEFAULT
    return light_theme(key) if light else THEMES[key]
