import { useMemo, useState } from "react";
import type { BuilderDefinition, BuilderSourceType, ParameterDefinition, TransformStepConfig } from "../types/transforms";

interface BuilderConfiguratorProps {
  title: string;
  sourceType: BuilderSourceType;
  builders: BuilderDefinition[];
  steps: TransformStepConfig[];
  onChange: (steps: TransformStepConfig[]) => void;
}

function cloneValue(value: unknown): unknown {
  if (value === undefined) {
    return null;
  }
  if (value === null || typeof value !== "object") {
    return value;
  }
  return JSON.parse(JSON.stringify(value));
}

function emptyValue(parameter: ParameterDefinition): unknown {
  if (parameter.default_value !== undefined) {
    return cloneValue(parameter.default_value);
  }
  if (parameter.kind === "boolean") {
    return false;
  }
  if (parameter.kind === "list") {
    return [];
  }
  if (parameter.kind === "object") {
    return {};
  }
  return null;
}

function defaultParams(builder: BuilderDefinition): Record<string, unknown> {
  return builder.parameters.reduce<Record<string, unknown>>((acc, parameter) => {
    acc[parameter.name] = emptyValue(parameter);
    return acc;
  }, {});
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "object") {
    return JSON.stringify(value, null, 2);
  }
  return String(value);
}

function parseValue(parameter: ParameterDefinition, value: string): unknown {
  if (value.trim() === "") {
    return null;
  }
  if (parameter.kind === "integer") {
    return Number.parseInt(value, 10);
  }
  if (parameter.kind === "number") {
    return Number.parseFloat(value);
  }
  if (parameter.kind === "boolean") {
    return value === "true";
  }
  if (parameter.kind === "list" || parameter.kind === "object" || value.trim().startsWith("[") || value.trim().startsWith("{")) {
    try {
      return JSON.parse(value);
    } catch {
      return value;
    }
  }
  return value;
}

function parameterInput(
  parameter: ParameterDefinition,
  value: unknown,
  onChange: (value: unknown) => void
) {
  if (parameter.kind === "boolean") {
    return (
      <label className="check-row compact-check">
        <input type="checkbox" checked={Boolean(value)} onChange={(event) => onChange(event.target.checked)} />
        <span>{parameter.name}</span>
      </label>
    );
  }

  if (parameter.options && parameter.options.length > 0) {
    return (
      <label className="field">
        <span>{parameter.name}</span>
        <select value={value == null ? "" : String(value)} onChange={(event) => onChange(parseValue(parameter, event.target.value))}>
          <option value="">null</option>
          {parameter.options.map((option) => (
            <option key={String(option)} value={String(option)}>
              {String(option)}
            </option>
          ))}
        </select>
      </label>
    );
  }

  if (parameter.kind === "list" || parameter.kind === "object") {
    return (
      <label className="field">
        <span>{parameter.name}</span>
        <textarea
          defaultValue={formatValue(value)}
          rows={parameter.kind === "object" ? 4 : 2}
          onBlur={(event) => onChange(parseValue(parameter, event.target.value))}
          placeholder={parameter.kind === "list" ? "[1, 2, 3]" : "{\"key\": \"value\"}"}
        />
      </label>
    );
  }

  return (
    <label className="field">
      <span>{parameter.name}</span>
      <input
        type={parameter.kind === "integer" || parameter.kind === "number" ? "number" : "text"}
        value={formatValue(value)}
        onChange={(event) => onChange(parseValue(parameter, event.target.value))}
        placeholder={parameter.required ? "required" : parameter.annotation ?? ""}
      />
    </label>
  );
}

export function BuilderConfigurator({ title, sourceType, builders, steps, onChange }: BuilderConfiguratorProps) {
  const [selectedBuilder, setSelectedBuilder] = useState("");
  const builderByName = useMemo(() => new Map(builders.map((builder) => [builder.name, builder])), [builders]);
  const selectableBuilder = selectedBuilder || builders[0]?.name || "";

  const addStep = () => {
    const builder = builderByName.get(selectableBuilder);
    if (!builder) {
      return;
    }
    onChange([...steps, { step: builder.name, params: defaultParams(builder), enabled: true, outputs: null }]);
  };

  const updateStep = (index: number, patch: Partial<TransformStepConfig>) => {
    onChange(steps.map((step, idx) => (idx === index ? { ...step, ...patch } : step)));
  };

  const updateParam = (index: number, name: string, value: unknown) => {
    const step = steps[index];
    updateStep(index, { params: { ...step.params, [name]: value } });
  };

  const removeStep = (index: number) => {
    onChange(steps.filter((_, idx) => idx !== index));
  };

  return (
    <section className="control-section">
      <h2>{title}</h2>
      <div className="field-grid two">
        <label className="field">
          <span>{sourceType} builder</span>
          <select value={selectableBuilder} onChange={(event) => setSelectedBuilder(event.target.value)}>
            {builders.map((builder) => (
              <option key={builder.name} value={builder.name}>
                {builder.name}
              </option>
            ))}
          </select>
        </label>
        <button className="secondary-button" type="button" onClick={addStep} disabled={!selectableBuilder}>
          Add
        </button>
      </div>

      <div className="step-list">
        {steps.map((step, index) => {
          const builder = builderByName.get(step.step);
          return (
            <div className="step-card" key={`${step.step}-${index}`}>
              <div className="step-card-header">
                <label className="check-row compact-check">
                  <input
                    type="checkbox"
                    checked={step.enabled}
                    onChange={(event) => updateStep(index, { enabled: event.target.checked })}
                  />
                  <span>{step.step}</span>
                </label>
                <button className="icon-button" type="button" onClick={() => removeStep(index)} title="Remove step">
                  x
                </button>
              </div>
              {builder?.docstring ? <p className="builder-doc">{builder.docstring.split("\n")[0]}</p> : null}
              <div className="param-grid">
                {(builder?.parameters ?? []).map((parameter) => (
                  <div key={parameter.name}>
                    {parameterInput(parameter, step.params[parameter.name], (value) => updateParam(index, parameter.name, value))}
                  </div>
                ))}
              </div>
              <label className="field">
                <span>Output mapping JSON</span>
                <textarea
                  defaultValue={step.outputs ? JSON.stringify(step.outputs, null, 2) : ""}
                  rows={2}
                  onBlur={(event) => {
                    const raw = event.target.value.trim();
                    if (!raw) {
                      updateStep(index, { outputs: null });
                      return;
                    }
                    try {
                      updateStep(index, { outputs: JSON.parse(raw) as Record<string, string> });
                    } catch {
                      updateStep(index, { outputs: step.outputs ?? null });
                    }
                  }}
                  placeholder='{"source_col": "renamed_col"}'
                />
              </label>
            </div>
          );
        })}
      </div>
    </section>
  );
}
