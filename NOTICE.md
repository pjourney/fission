# Fission provenance

Fission is based on the FreeCAD open-source project. FreeCAD and its contributors
retain their copyrights. Fission is an independent derivative and is not endorsed
by FreeCAD or Autodesk. No Autodesk source, application assets, icons or logos are
included. Public documentation informs interaction mappings only.

## Source baseline

- FreeCAD: https://github.com/FreeCAD/FreeCAD
- Revision: `c1c0b506213e072d6f1498739abb1c3890159426` (27.1 development)
- Root license: GNU LGPL 2.1; individual FreeCAD files generally specify
  `LGPL-2.1-or-later`. Original notices remain in the checkout and source patches.
- Recursive submodules: GSL, OndselSolver, FreeCAD Coin, FreeCAD Pivy and
  AddonManager, including Coin's own submodules. The source lock records commits.
- FreeCAD's AI policy and contribution rules were inspected. This independent
  fork is AI-assisted; no upstream submission is authorized or performed.
- Newly authored Fission files identify their licenses with SPDX headers:
  shell/workbench/build code uses the existing MIT repository license; Browser,
  Timeline, history, search and shortcuts use LGPL as stated in each file.
  Engine modifications retain their original licenses.

## Dependencies

The Windows build uses the official FreeCAD LibPack 3.5.5, x64 Release, from
https://github.com/FreeCAD/FreeCAD-LibPack/releases/tag/3.5.5 . It supplies Qt,
PySide, Python, OpenCASCADE, Boost and other dependencies. Their bundled license
and copyright notices must accompany any distributed runtime. Source provenance
and exact download/hash are recorded by setup. Dynamic libraries remain separate
and replaceable. A binary distribution must also include the pinned FreeCAD
source, recursive dependency source, Fission source and applied source patches
(or a compliant durable source offer). Do not publish a binary-only archive.

Core third-party source licenses are preserved in `upstream-src/src/3rdParty`:
Microsoft GSL (MIT), OndselSolver (LGPL), Coin (BSD), Pivy (per-file LGPL/BSD),
Clipper2 (Boost), lru-cache (MIT), libkdtree (LGPL), libE57Format (Boost).
Use the individual checked-out license texts for authoritative component terms.
No optional Sheet Metal addon is bundled. The tab is offered only if compatible
commands are actually installed; integration/provenance review remains required.

See `licenses/FreeCAD-LGPL-2.1.txt` and the original FreeCAD source for attribution.
