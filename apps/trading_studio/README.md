# Trading Studio

New visual experiment-authoring application. The existing
`apps/trading_dashboard` remains the legacy dashboard and is intentionally
unchanged.

## Run locally

```bash
cd apps/trading_studio
npm ci
npm run dev
```

The development server runs on `http://127.0.0.1:5174`.

## Current scope

- Add components by click or drag, move and delete canvas nodes, and use
  undo/redo with the toolbar or keyboard shortcuts.
- Toggle the Components library from the header menu button.
- Select nodes and configure, duplicate, enable/disable, reorder, or remove
  their settings in the inspector.
- Configure feature parameters, nested normalizations, helpers/transforms, and
  output mappings.
- Rename and locally autosave the versioned Studio document.
- Inspect and copy synchronized Studio YAML.
- Validate pipeline order, required components, fields, and causal shifts.
- Run a deterministic local Studio workflow against the bundled preview rows.
- Inspect descriptive sample metrics and a responsive, selectable multi-series
  preview chart.
- Preview data and see validation/results states.

The local run compiles and validates the Studio document. It is intentionally
reported as a local preview and does not claim to execute a framework backtest
or produce OOS trading metrics. Framework execution requires a separate,
explicit API contract for submitting fully resolved experiment configs.
