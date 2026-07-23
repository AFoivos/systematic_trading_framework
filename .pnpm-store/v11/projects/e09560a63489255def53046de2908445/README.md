# Trading Studio

New visual experiment-authoring application. The existing
`apps/trading_dashboard` remains the legacy dashboard and is intentionally
unchanged.

## Run locally

```powershell
cd apps/trading_studio
npm install
npm run dev
```

The development server runs on `http://127.0.0.1:5174`.

## Current scope

- Drag components from the library onto the experiment canvas.
- Select nodes and configure them in the inspector.
- Configure feature parameters, nested normalizations, helpers/transforms, and
  output mappings.
- Inspect synchronized YAML.
- Validate the experiment and run a local simulated workflow.
- Preview data and see validation/results states.

The UI is intentionally backend-agnostic in this first slice. It establishes
the experiment document and interaction model before wiring run execution to
the framework services.
