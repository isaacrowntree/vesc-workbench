#!/usr/bin/env python3
"""Buttons: bounce, hold and repeat, driven by a fake clock."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from screens.input import Buttons, UP, DOWN, ENTER, HOLD    # noqa: E402

fails = []


def check(name, cond, detail=""):
    if cond:
        print("  PASS  %s" % name)
    else:
        fails.append(name)
        print("  FAIL  %s %s" % (name, detail))


class Rig:
    def __init__(self):
        self.t = 0
        self.pins = [False, False, False]
        self.b = Buttons(lambda: tuple(self.pins), lambda: self.t)

    def at(self, t, up=None, down=None, enter=None):
        self.t = t
        for i, v in enumerate((up, down, enter)):
            if v is not None:
                self.pins[i] = v
        return self.b.poll()


def main():
    print("== a clean press fires once")
    r = Rig()
    check("nothing at rest", r.at(0) == [])
    check("press fires", r.at(100, down=True) == [DOWN])
    check("still held fires nothing", r.at(150) == [])
    check("release is silent", r.at(200, down=False) == [])

    print("== contact bounce does not fire twice")
    r = Rig()
    r.at(100, down=True)
    check("bounce off is ignored", r.at(120, down=False) == [])
    check("bounce on is ignored", r.at(140, down=True) == [])
    check("and no extra event later", r.at(200) == [])

    print("== enter acts on release, so a hold is distinguishable")
    r = Rig()
    check("press alone does nothing", r.at(100, enter=True) == [])
    check("release fires enter", r.at(400, enter=False) == [ENTER])

    print("== holding enter fires hold at the firmware's 3 s threshold")
    r = Rig()
    r.at(100, enter=True)
    check("not at 1 s", r.at(1100) == [])
    check("not at 2.9 s", r.at(2999) == [])
    check("hold fires at 3 s", r.at(3200) == [HOLD])
    check("no second hold", r.at(4000) == [])
    check("release adds nothing", r.at(4500, enter=False) == [])

    print("== up and down auto-repeat when held")
    r = Rig()
    check("first press", r.at(100, up=True) == [UP])
    check("nothing before the repeat delay", r.at(400) == [])
    check("repeats after the delay", r.at(650) == [UP])
    check("keeps repeating", r.at(810) == [UP])
    check("but not faster than the interval", r.at(830) == [])

    print("== two buttons at once both report")
    r = Rig()
    check("both fire", sorted(r.at(100, up=True, down=True)) == [DOWN, UP])

    print("== repeat can be turned off")
    r = Rig()
    r.b.repeat = False
    r.at(100, down=True)
    check("no repeat when disabled", r.at(1200) == [])

    print()
    if fails:
        print("%d INPUT TESTS FAILED" % len(fails))
        return 1
    print("all input tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
