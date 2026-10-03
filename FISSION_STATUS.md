# Fission status

This is an active development build. Alpha acceptance is recorded only after the
native application, CAD workflows and primary shortcut tests pass. It is not
declared complete from source inspection or pure unit tests alone.

## Implemented, awaiting integrated native acceptance

- Pinned recursive FreeCAD source, official hashed Windows LibPack, reproducible
  native build scripts, independent branch/remotes and attribution.
- Fission native executable/product resources, original mark/splash, About,
  isolated application identity and default Design workspace.
- Compact grouped Solid/Surface/Mesh/Assembly/Utilities tabs and Sketch context.
- Real component/body creation, native task previews/editors and FCStd model.
- Incremental Browser and horizontal feature Timeline with selection/editing,
  native error status, safe suppression and dependency explanations.
- Verified Fusion default profiles, contextual dispatch, collision priority,
  native shortcut preferences, customization/JSON import/export and S launcher.
- Fission navigation preset retaining native camera/SpaceMouse support; native
  orientation cube, view buttons, scoped dark/light appearance and layout saving.
- Local welcome screen, recent/open/import/save actions and native extensions.

## Current validation

Untouched native source build and integrated acceptance tests are in progress.
Pure history tests and real Qt shortcut event tests pass. Final counts and native
CAD/serialization/interchange/navigation results will replace this paragraph.

## Partial functionality and known differences

- Native FreeCAD feature task panels share a common dock/theme, but their fields
  and geometry semantics are retained. Fusion Press Pull maps to sketch Extrude;
  general face offset, Fusion replay/rollback and universal feature reordering
  are not implemented.
- Move / Copy offers transactional translation/parametric linked copies plus
  native canvas Transform. Assembly joints use actual FreeCAD joint types; no
  equivalent as-built joint is claimed.
- Specialist Drawing and Manufacture currently open native workspaces. Full
  Fission presentation and persistent shortcut context there are next priorities.
- Sheet Metal is not bundled. Its tab requires available addon commands and any
  bundled addon requires provenance/license/version review.
- Selection modes, cloud/comments/data panel, midpoint modifier and several
  specialty Fusion commands have documented gaps. Unsupported defaults are
  reserved and explained instead of reusing conflicting native shortcuts.
- Source build uses a development FreeCAD pin and newer installed compiler;
  stability/test differences must be recorded against the untouched baseline.

## Next priorities

Complete native Alpha acceptance and fix observed failures; refine specialist
workspaces and geometry-aware command panels; expand matching selection/marking
menus; verify extension integration; package with matching source/notices.
