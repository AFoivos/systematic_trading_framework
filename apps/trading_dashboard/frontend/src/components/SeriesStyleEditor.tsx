import type { VisualizationConfig, RenderType, ChartTarget } from "../types/visualization";
import { seriesKey } from "../utils/transforms";

interface SeriesStyleEditorProps {
  configs: VisualizationConfig[];
  activeKey: string | null;
  onSelect: (key: string) => void;
  onUpdate: (key: string, patch: Partial<VisualizationConfig>) => void;
}

const renderTypes: RenderType[] = [
  "line",
  "area",
  "histogram",
  "horizontal_level",
  "prediction_line",
  "probability_band"
];
const chartTargets: ChartTarget[] = ["main_price_chart", "lower_panel"];

export function SeriesStyleEditor({ configs, activeKey, onSelect, onUpdate }: SeriesStyleEditorProps) {
  const active = configs.find((config) => seriesKey(config.source_type, config.series_id) === activeKey) ?? configs[0];
  if (!active) {
    return (
      <aside className="right-panel">
        <h2>Series</h2>
        <p className="empty-copy">No selected series.</p>
      </aside>
    );
  }
  const key = seriesKey(active.source_type, active.series_id);

  return (
    <aside className="right-panel">
      <h2>Series</h2>
      <label className="field">
        <span>Selected</span>
        <select value={key} onChange={(event) => onSelect(event.target.value)}>
          {configs.map((config) => {
            const optionKey = seriesKey(config.source_type, config.series_id);
            return (
              <option key={optionKey} value={optionKey}>
                {config.display_name}
              </option>
            );
          })}
        </select>
      </label>
      <label className="check-row toggle-row">
        <input
          type="checkbox"
          checked={active.visible}
          onChange={(event) => onUpdate(key, { visible: event.target.checked })}
        />
        <span>Visible</span>
      </label>
      <label className="field">
        <span>Render type</span>
        <select value={active.render_type} onChange={(event) => onUpdate(key, { render_type: event.target.value as RenderType })}>
          {renderTypes.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>Placement</span>
        <select value={active.chart_target} onChange={(event) => onUpdate(key, { chart_target: event.target.value as ChartTarget })}>
          {chartTargets.map((target) => (
            <option key={target} value={target}>
              {target}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>Panel</span>
        <input
          placeholder="empty = own panel / shared name"
          value={active.panel_id ?? ""}
          onChange={(event) => onUpdate(key, { panel_id: event.target.value || null })}
        />
        <small className="field-hint">Leave empty for a dedicated feature panel. Reuse the same name to stack series together.</small>
      </label>
      <label className="field">
        <span>Color</span>
        <input
          type="color"
          value={active.style.color ?? "#0f766e"}
          onChange={(event) => onUpdate(key, { style: { ...active.style, color: event.target.value } })}
        />
      </label>
      <label className="field">
        <span>Line width</span>
        <input
          type="number"
          min="1"
          max="5"
          value={active.style.lineWidth ?? 2}
          onChange={(event) => onUpdate(key, { style: { ...active.style, lineWidth: Number(event.target.value) } })}
        />
      </label>
    </aside>
  );
}
