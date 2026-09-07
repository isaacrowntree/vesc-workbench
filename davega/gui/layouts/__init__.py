"""Nine arrangements of the same numbers.

A theme is a palette *and* a layout - `themes.py` has always declared both, and
until now only the palette was read. The layout is the part that makes Rosso a
tachometer and Nevera a power meter rather than the same dashboard in another
colour.

Only the selected layout is imported. Nine modules resident at once is a
MemoryError on a board with 98 kB of heap, and a rider uses one.
"""

NAMES = ("flagship", "dial", "shards", "hairline", "bare", "flow", "eco",
         "minimal", "rail", "rings")

DEFAULT = "flagship"


def load(name):
    """The Layout class for a layout name, imported on demand.

    Any other layout already resident is dropped first, and dropping one takes
    two steps rather than the obvious one. Removing it from `sys.modules` is
    not enough: importing `gui.layouts.dial` also binds `dial` as an attribute
    of this package, and that reference keeps the whole module alive. Every
    theme a rider tried stayed in memory, about nine kilobytes each, until the
    board ran out - which looked like the dashboard dying on a theme change
    and handing the screen back to the stock app.
    """
    if name not in NAMES:
        name = DEFAULT
    pkg = __name__                      # gui.layouts, host or device
    keep = (pkg, pkg + ".kit", pkg + "." + name)
    import sys
    me = sys.modules[pkg]
    for other in NAMES:
        if other == name:
            continue
        if (pkg + "." + other) in sys.modules:
            del sys.modules[pkg + "." + other]
        if hasattr(me, other):
            delattr(me, other)          # the reference that actually held it
    try:
        import gc
        gc.collect()
    except ImportError:                 # not every host has it
        pass

    mod = __import__(pkg + "." + name, None, None, (name,))
    if not hasattr(mod, "Layout"):      # MicroPython hands back the package
        mod = getattr(mod, name)
    return mod.Layout


class Base:
    """What a layout has to answer.

    The screen (`s`) is passed in rather than subclassed so that a layout is a
    description of an arrangement and nothing else: it owns no state, holds no
    display, and can be swapped at runtime when the rider changes theme.
    """

    #: regions deliberately off the column grid, each with its reason
    grid_exceptions = {}
    #: pairs that deliberately share space, because they never draw at once
    overlap_exceptions = set()
    #: the riding screen usually takes the footer strip for its own readout
    shows_page_dots = False

    #: name -> (frames, snap) for the values that move smoothly
    tweens = {}

    def target(self, key, s, f, b):
        """Where a tweened value is heading, this frame."""
        return 0.0

    def chrome(self, s, d):
        """Furniture: painted once, on a full repaint."""

    def regions(self, s):
        """The live parts, as (name, x, y, w, h, value, painter) tuples."""
        return ()
