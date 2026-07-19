# Overlay architecture

The editable hardware overlays are split by responsibility:

- `infrastructure/` owns the modal shell, lifecycle, one-active-overlay policy
  and target-revision session.
- `components/` contains reusable Kivy controls and visual building blocks.
- `features/` owns feature state adapters and feature-specific presentation.
- Header controls and tiles import their feature overlays directly.

## Data flow

1. A header control or tile opens an `OverlayKey` through `OverlayManager`.
2. `ControlOverlay` reads the latest online snapshot and never sends on open.
3. A feature adapter converts protocol dictionaries into an immutable state.
4. The feature overlay renders live values and applies confirmed target values.
5. User changes submit a feature-owned target patch through `OverlayCommandEngine`.
6. `RevisionSession` remains pending until the ESP mirrors the revision.
7. A retry resends the stored command envelope with the same revision.



## Circulation fan instances

One overlay class handles every generated circulation fan. `fan_id` is part of
the `OverlayKey`, snapshot adapter and command channel. No per-fan classes or
files are generated.
