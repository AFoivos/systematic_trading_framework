import { useState } from "react";
import type { LayoutSummary } from "../types/visualization";

interface LayoutManagerProps {
  layouts: LayoutSummary[];
  onSave: (name: string) => void;
  onLoad: (layoutId: string) => void;
}

export function LayoutManager({ layouts, onSave, onLoad }: LayoutManagerProps) {
  const [name, setName] = useState("research-layout");
  const [selectedLayout, setSelectedLayout] = useState("");
  return (
    <section className="control-section">
      <h2>Layouts</h2>
      <div className="field-grid two">
        <label className="field">
          <span>Name</span>
          <input value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <button className="primary-button" type="button" onClick={() => onSave(name)}>
          Save
        </button>
      </div>
      <div className="field-grid two">
        <label className="field">
          <span>Saved</span>
          <select value={selectedLayout} onChange={(event) => setSelectedLayout(event.target.value)}>
            <option value="">Choose</option>
            {layouts.map((layout) => (
              <option key={layout.layout_id} value={layout.layout_id}>
                {layout.name}
              </option>
            ))}
          </select>
        </label>
        <button className="secondary-button" type="button" disabled={!selectedLayout} onClick={() => onLoad(selectedLayout)}>
          Load
        </button>
      </div>
    </section>
  );
}

