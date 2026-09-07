# Keeping the firmware alive

DAVEGA closed in 2024. The update endpoints still answer, and one day they will
not. This is what to grab, what it hashes to, and what may and may not be
passed on.

## The DAVEGA X images

Archived locally, on **2026-09-07**, from the vendor's own update index at
`https://davega.eu/fw/index_v5.json` — which still lists eight releases,
including a **v5.07rc3 dated 2025-03-11** that came out after the shop closed
and was never announced.

| File | Released | Bytes | SHA-256 |
|---|---|---|---|
| `davegax-app-v5.07rc3.bin` | 2025/03/11 | 1562448 | `5596c1b3d02d62191a80b2e4a462abbc2b83e9801b80261344f20fbaee5fd5b3` |
| `davegax-app-v5.06.bin` | 2023/05/15 | 1562320 | `fa52c8192141d74f0172708cc3aae6062fa7123a5a3c7fdc3892447e53114721` |
| `davegax-app-v5.05.bin` | 2022/10/10 | 1561408 | `ffb6d524722e3ef1428365bf8d36731ddc93c6d8957f57f63f651e8b1ce92660` |
| `davegax-app-v5.04.bin` | 2022/04/21 | 1561376 | `58b66ec705f040d56ec315773447bfba40f82d08d382f3af380d63d7bbbf3749` |
| `davegax-app-v5.03.bin` | 2022/01/10 | 1559328 | `0f485072ba951fc544d3903acbadc5b767efdc12f6ede533ecfeafb8713697bb` |
| `davegax-app-v5.02.bin` | 2021/12/14 | 1553952 | `2d2fd11875d6c462dc342bdb6255b783788b83896296e456ddbf467d83d4a27e` |
| `davegax-app-v5.01.bin` | 2021/11/09 | 1551392 | `b15dafa1389f38b84a823c54ddc8329f1d62c82a9cf03e52d0aa5b501c087eef` |
| `davegax-app-v5.00.bin` | 2021/11/08 | 1502736 | `007342f76faf2491f8f6f7576aadc1f60c65dbc88d461d4a40179460df594df3` |
| `davegax-firmware-v5.01.bin` (full image) | 2021/11/09 | 1612832 | `6bc74ebba64530d9d54f073965c1e7418c406e00ee387767277f064948772cea` |

Fetch them yourself with:

```sh
curl -O https://davega.eu/fw/index_v5.json
curl -O https://davega.eu/fw/davegax-app-v5.07rc3.bin      # and the rest
curl -O https://davega.eu/fw/davegax-firmware-v5.01.bin    # full image
```

**The binaries are not in this repository, and the hashes are the point.**
DAVEGA's application firmware is proprietary and closed. A company ceasing to
trade does not release its copyright: it persists for decades and passes to
whoever holds the assets — a buyer, the founder, an administrator.
"Abandonware" is a community norm, not a legal category, and this repository is
MIT and public.

What can be published is the *manifest*. If davega.eu goes dark and a copy of
`v5.06` turns up on a forum, the SHA-256 above is what tells you whether it is
the image the vendor actually shipped or something somebody built. That is most
of the preservation value and none of the redistribution.

Keep your own copy. `/firmware/` is gitignored for exactly this.

## The parts of DAVEGA that *are* free

The **DAVEga Arduino firmware** — the earlier, open hardware — is
[GPL-3.0 on GitHub](https://github.com/janpom/davega) and can be forked,
mirrored and redistributed freely. It is also the reference this project reads
for the wire protocol, the button timings and the Unity packet layout. Nothing
about it is at risk.

The DAVEGA X's *application* is the closed part.

## VESC firmware is a different matter entirely

The VESC firmware is **GPL-3.0**, stated in the header of every source file:

> This file is part of the VESC firmware. The VESC firmware is free software:
> you can redistribute it and/or modify it under the terms of the GNU General
> Public License as published by the Free Software Foundation, either version 3
> of the License, or (at your option) any later version.

So:

- **It cannot disappear.** `vedderb/bldc` has thousands of forks, and the
  licence guarantees anyone may mirror it. This repository already depends on
  that: `lisp/tests/protocol-diff.sh` checks the wire format against upstream
  `6.00` and `master` on every CI run.
- **It can be rebuilt.** A binary is a convenience; the source plus a toolchain
  is the real archive, and both are freely available.
- **It can be redistributed**, unlike the DAVEGA images — including by this
  repository, if that ever became useful.

The one thing worth keeping locally is the exact binary running on your board,
so a bricked ESC can be put back to a known state without rebuilding:
VESC Tool ships the images it flashes, and `make probe` records which version
is on the controller.

## What is on this board

| | |
|---|---|
| ESC | FOCBOX Unity, hw target `UNITY`, firmware **7.00** |
| STM32 | lot `Q816514`, wafer 18, die (75, 59) — see [provenance](board-provenance.md) |
| Display | DAVEGA X, stock app replaced by [ours](../davega/README.md) |
