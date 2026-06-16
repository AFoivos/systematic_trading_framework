import { useMemo, useState } from "react";
import type { BuilderDefinition, BuilderSourceType, ParameterDefinition, TransformStepConfig } from "../types/transforms";

interface BuilderConfiguratorProps {
  title: string;
  sourceType: BuilderSourceType;
  builders: BuilderDefinition[];
  steps: TransformStepConfig[];
  onChange: (steps: TransformStepConfig[]) => void;
}

const TRANSFORM_KIND_OPTIONS = ["rolling_stat", "rolling_zscore", "rolling_clip", "ratio", "tsfresh_rolling"] as const;
const NESTED_TRANSFORM_KIND_OPTIONS = ["rolling_stat", "rolling_zscore", "rolling_clip", "tsfresh_rolling"] as const;
const ROLLING_STAT_MODE_OPTIONS = [
  "root_mean_square",
  "mean",
  "standard_deviation",
  "variance",
  "median",
  "sum_values",
  "minimum",
  "maximum",
  "absolute_maximum",
  "mad",
  "iqr",
  "skew",
  "kurtosis",
  "slope"
] as const;

type FeatureTransformConfig = Record<string, unknown>;

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

function transformOutputCol(kind: string, sourceCol: string, mode = "root_mean_square"): string {
  if (!sourceCol) {
    return "";
  }
  if (kind === "rolling_zscore") {
    return `${sourceCol}__zscore`;
  }
  if (kind === "rolling_clip") {
    return `${sourceCol}__rolling_clip`;
  }
  return `${sourceCol}__${mode}`;
}

function defaultFeatureTransform(kind = "rolling_stat", sourceCol = "close_logret", secondarySourceCol = ""): FeatureTransformConfig {
  if (kind === "ratio") {
    const denominatorCol = secondarySourceCol || sourceCol;
    return {
      kind,
      numerator_col: sourceCol,
      denominator_col: denominatorCol,
      output_col: sourceCol && denominatorCol ? `${sourceCol}_over_${denominatorCol}` : "",
      eps: 1e-8
    };
  }
  if (kind === "rolling_clip") {
    return {
      kind,
      source_col: sourceCol,
      output_col: transformOutputCol(kind, sourceCol),
      window: 2520,
      lower_q: 0.01,
      upper_q: 0.99,
      shift: 1
    };
  }
  if (kind === "rolling_zscore") {
    return {
      kind,
      source_col: sourceCol,
      output_col: transformOutputCol(kind, sourceCol),
      window: 2520,
      shift: 1
    };
  }
  if (kind === "tsfresh_rolling") {
    return {
      kind,
      source_col: sourceCol,
      output_prefix: sourceCol,
      window: 48,
      shift: 0,
      calculators: ["root_mean_square"]
    };
  }
  return {
    kind: "rolling_stat",
    source_col: sourceCol,
    mode: "root_mean_square",
    window: 48,
    shift: 0,
    output_col: transformOutputCol("rolling_stat", sourceCol, "root_mean_square")
  };
}

function defaultBulkFeatureTransform(kind = "rolling_stat"): FeatureTransformConfig {
  if (kind === "rolling_clip") {
    return {
      kind,
      window: 2520,
      lower_q: 0.01,
      upper_q: 0.99,
      shift: 1
    };
  }
  if (kind === "rolling_zscore") {
    return {
      kind,
      window: 2520,
      shift: 1
    };
  }
  if (kind === "tsfresh_rolling") {
    return {
      kind,
      window: 48,
      shift: 0,
      calculators: ["root_mean_square"]
    };
  }
  return {
    kind: "rolling_stat",
    mode: "root_mean_square",
    window: 48,
    shift: 0
  };
}

function preferredSourceColumn(sourceColumns?: string[]): string {
  return sourceColumns && sourceColumns.length > 0 ? sourceColumns[0] : "close_logret";
}

function secondarySourceColumn(sourceColumns?: string[]): string {
  return sourceColumns && sourceColumns.length > 1 ? sourceColumns[1] : "";
}

function featureTransformsFromParams(params: Record<string, unknown>, sourceColumns?: string[]): FeatureTransformConfig[] {
  const raw = params.transforms;
  if (!Array.isArray(raw) || raw.length === 0) {
    return [defaultFeatureTransform("rolling_stat", preferredSourceColumn(sourceColumns), secondarySourceColumn(sourceColumns))];
  }
  return raw.map((item) =>
    item && typeof item === "object" && !Array.isArray(item)
      ? { ...item } as FeatureTransformConfig
      : defaultFeatureTransform("rolling_stat", preferredSourceColumn(sourceColumns), secondarySourceColumn(sourceColumns))
  );
}

function bulkFeatureTransform(transform: FeatureTransformConfig): FeatureTransformConfig {
  const kind = stringValue(transform.kind, "rolling_stat");
  if (!NESTED_TRANSFORM_KIND_OPTIONS.includes(kind as typeof NESTED_TRANSFORM_KIND_OPTIONS[number])) {
    return defaultBulkFeatureTransform();
  }
  const {
    source_col: _sourceCol,
    source_selector: _sourceSelector,
    numerator_col: _numeratorCol,
    numerator_selector: _numeratorSelector,
    denominator_col: _denominatorCol,
    denominator_selector: _denominatorSelector,
    output_col: _outputCol,
    output_prefix: _outputPrefix,
    eps: _eps,
    ...rest
  } = transform;
  return rest;
}

function bulkFeatureTransformsFromParams(params: Record<string, unknown>): FeatureTransformConfig[] {
  const raw = params.transforms;
  if (!Array.isArray(raw) || raw.length === 0) {
    return [defaultBulkFeatureTransform()];
  }
  return raw.map((item) =>
    item && typeof item === "object" && !Array.isArray(item)
      ? bulkFeatureTransform({ ...item } as FeatureTransformConfig)
      : defaultBulkFeatureTransform()
  );
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

function stringValue(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function numericInputValue(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value) ? String(value) : "";
}

function parseNumericInput(value: string, integer = false): number | null {
  if (value.trim() === "") {
    return null;
  }
  const parsed = integer ? Number.parseInt(value, 10) : Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function parseListValue(value: string): unknown[] {
  const trimmed = value.trim();
  if (!trimmed) {
    return [];
  }
  try {
    const parsed = JSON.parse(trimmed);
    return Array.isArray(parsed) ? parsed : [parsed];
  } catch {
    return trimmed.split(",").map((item) => item.trim()).filter(Boolean);
  }
}

function uniqueStrings(values: string[]): string[] {
  return values.filter((value, index) => value.length > 0 && values.indexOf(value) === index);
}

function asString(value: unknown, fallback: string): string {
  return typeof value === "string" && value.length > 0 ? value : fallback;
}

function asBoolean(value: unknown, fallback: boolean): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function asInteger(value: unknown, fallback: number): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.trunc(value);
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) ? parsed : fallback;
  }
  return fallback;
}

function optionalInteger(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.trunc(value);
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function asNumber(value: unknown, fallback: number): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }
  return fallback;
}

function asIntegerList(value: unknown, fallback: number[]): number[] {
  const rawValues = Array.isArray(value) ? value : typeof value === "string" && value.trim() ? parseListValue(value) : fallback;
  const parsed = rawValues
    .map((item) => asInteger(item, Number.NaN))
    .filter((item) => Number.isFinite(item) && item > 0);
  return parsed.length > 0 ? uniqueStrings(parsed.map(String)).map((item) => Number.parseInt(item, 10)) : fallback;
}

function asStringList(value: unknown, fallback: string[]): string[] {
  const rawValues = Array.isArray(value) ? value : typeof value === "string" && value.trim() ? parseListValue(value) : fallback;
  const parsed = rawValues.map((item) => String(item)).filter(Boolean);
  return parsed.length > 0 ? uniqueStrings(parsed) : fallback;
}

function formatTemplate(template: unknown, fallback: string, replacements: Record<string, string | number>): string {
  if (typeof template !== "string" || !template.trim()) {
    return fallback;
  }
  return Object.entries(replacements).reduce(
    (current, [key, value]) => current.split(`{${key}}`).join(String(value)),
    template
  );
}

function outputOrParam(params: Record<string, unknown>, key: string, fallback: string): string {
  return asString(params[key], fallback);
}

function builderDisplayName(builder?: BuilderDefinition): string {
  return builder?.display_name || builder?.name || "";
}

function compactColumnList(columns: string[], limit = 6): string {
  if (columns.length <= limit) {
    return columns.join(", ");
  }
  return `${columns.slice(0, limit).join(", ")} +${columns.length - limit}`;
}

function deriveFeatureOutputColumns(stepName: string, params: Record<string, unknown>): string[] {
  const priceCol = asString(params.price_col, "close");
  const closeCol = asString(params.close_col, "close");
  const returnsCol = asString(params.returns_col, "close_logret");
  const window = asInteger(params.window, 20);

  switch (stepName) {
    case "returns":
      return [asString(params.col_name, asBoolean(params.log, false) ? "close_logret" : "close_ret")];
    case "volatility":
      return [
        ...asIntegerList(params.rolling_windows, [10, 20, 60]).map((item) => `vol_rolling_${item}`),
        ...asIntegerList(params.ewma_spans, [10, 20]).map((item) => `vol_ewma_${item}`)
      ];
    case "trend":
      return uniqueStrings([
        ...asIntegerList(params.sma_windows, [20, 50, 200]).flatMap((item) => [
          formatTemplate(params.sma_col_template, `${priceCol}_sma_${item}`, { price_col: priceCol, window: item, span: item }),
          `${priceCol}_over_sma_${item}`
        ]),
        ...asIntegerList(params.ema_spans, [20, 50]).flatMap((item) => [
          formatTemplate(params.ema_col_template, `${priceCol}_ema_${item}`, { price_col: priceCol, window: item, span: item }),
          `${priceCol}_over_ema_${item}`
        ])
      ]);
    case "trend_regime": {
      const base = asInteger(params.base_sma_for_sign, 50);
      const short = asInteger(params.short_sma, 20);
      const long = asInteger(params.long_sma, 50);
      return uniqueStrings([
        ...[base, short, long].flatMap((item) => [`${priceCol}_sma_${item}`, `${priceCol}_over_sma_${item}`]),
        `${priceCol}_trend_regime_sma_${base}`,
        `${priceCol}_trend_state_sma_${short}_${long}`
      ]);
    }
    case "bollinger": {
      const nStd = asNumber(params.n_std, 2.0);
      return [`bb_ma_${window}`, `bb_upper_${window}_${nStd}`, `bb_lower_${window}_${nStd}`, `bb_width_${window}_${nStd}`, `bb_percent_b_${window}_${nStd}`];
    }
    case "macd": {
      const fast = asInteger(params.fast, 12);
      const slow = asInteger(params.slow, 26);
      const signal = asInteger(params.signal, 9);
      return [`macd_${fast}_${slow}`, `macd_signal_${signal}`, `macd_hist_${fast}_${slow}_${signal}`];
    }
    case "ppo": {
      const fast = asInteger(params.fast, 12);
      const slow = asInteger(params.slow, 26);
      const signal = asInteger(params.signal, 9);
      return [
        outputOrParam(params, "ppo_col", `ppo_${fast}_${slow}`),
        outputOrParam(params, "ppo_signal_col", `ppo_signal_${signal}`),
        outputOrParam(params, "ppo_hist_col", `ppo_hist_${fast}_${slow}_${signal}`)
      ];
    }
    case "roc":
      return asIntegerList(params.windows, [10, 20]).map((item) => `roc_${item}`);
    case "atr": {
      const windows = asIntegerList(params.windows, [asInteger(params.window, 14)]);
      return windows.flatMap((item) => [
        outputOrParam(params, "atr_col", `atr_${item}`),
        ...(asBoolean(params.add_over_price, true) ? [outputOrParam(params, "over_price_col", `atr_over_price_${item}`)] : [])
      ]);
    }
    case "adx":
      return asIntegerList(params.windows, [asInteger(params.window, 14)]).flatMap((item) => [`plus_di_${item}`, `minus_di_${item}`, `adx_${item}`]);
    case "volume_features": {
      const atrWindow = asInteger(params.atr_window, 14);
      return [`volume_z_${asInteger(params.vol_z_window, 20)}`, outputOrParam(params, "atr_col", `atr_${atrWindow}`), `volume_over_atr_${atrWindow}`];
    }
    case "vwap": {
      const windows = asIntegerList(params.windows, [asInteger(params.window, 20)]);
      return windows.flatMap((item) => [
        outputOrParam(params, "vwap_col", `vwap_${item}`),
        ...(asBoolean(params.add_distance, true) ? [outputOrParam(params, "distance_col", `${closeCol}_over_vwap_${item}`)] : [])
      ]);
    }
    case "mfi":
      return [`mfi_${asInteger(params.window, 14)}`];
    case "rsi":
      return asIntegerList(params.windows, [14]).map((item) => `${priceCol}_rsi_${item}`);
    case "stochastic": {
      const stochWindow = asInteger(params.window, 14);
      return [`${priceCol}_stoch_k_${stochWindow}`, `${priceCol}_stoch_d_${stochWindow}`];
    }
    case "stochastic_rsi": {
      const prefix = asString(params.prefix, "stoch_rsi");
      return [
        `${prefix}_k`,
        `${prefix}_d`,
        `${prefix}_k_minus_d`,
        `${prefix}_cross_up`,
        `${prefix}_cross_down`,
        `${prefix}_oversold`,
        `${prefix}_overbought`,
        `${prefix}_slope`,
        `${prefix}_recover_from_oversold`,
        `${prefix}_fall_from_overbought`
      ];
    }
    case "price_momentum":
      return asIntegerList(params.windows, [5, 20, 60]).map((item) => `${priceCol}_mom_${item}`);
    case "return_momentum":
      return asIntegerList(params.windows, [5, 20, 60]).map((item) => `${returnsCol}_mom_${item}`);
    case "vol_normalized_momentum":
      return asIntegerList(params.windows, [5, 20, 60]).map((item) => `${returnsCol}_norm_mom_${item}`);
    case "mama":
      return [outputOrParam(params, "output_col", "mama")];
    case "fama":
      return [outputOrParam(params, "output_col", "fama")];
    case "dominant_cycle_period":
      return [outputOrParam(params, "output_col", "dominant_cycle_period")];
    case "dominant_cycle_phase":
      return [outputOrParam(params, "output_col", "dominant_cycle_phase")];
    case "instantaneous_trendline": {
      const outputCol = outputOrParam(params, "output_col", "instantaneous_trendline");
      return [
        outputCol,
        ...(asBoolean(params.add_trigger, true)
          ? [outputOrParam(params, "trigger_col", `${outputCol}_trigger`)]
          : [])
      ];
    }
    case "fisher_transform": {
      const fisherWindow = asInteger(params.window, 10);
      const outputCol = outputOrParam(params, "output_col", `fisher_transform_${fisherWindow}`);
      return [
        outputCol,
        ...(asBoolean(params.add_signal, true)
          ? [outputOrParam(params, "signal_col", `${outputCol}_signal`)]
          : [])
      ];
    }
    case "inverse_fisher_transform":
      return [outputOrParam(params, "output_col", `inverse_fisher_transform_${window}`)];
    case "sinewave_indicator":
      return [
        outputOrParam(params, "output_col", "sinewave"),
        outputOrParam(params, "lead_output_col", "lead_sinewave")
      ];
    case "cyber_cycle": {
      const outputCol = outputOrParam(params, "output_col", "cyber_cycle");
      return [
        outputCol,
        ...(asBoolean(params.add_trigger, true)
          ? [outputOrParam(params, "trigger_col", `${outputCol}_trigger`)]
          : [])
      ];
    }
    case "decycler":
      return [outputOrParam(params, "output_col", `decycler_${asInteger(params.period, 60)}`)];
    case "decycler_oscillator":
      return [
        outputOrParam(
          params,
          "output_col",
          `decycler_oscillator_${asInteger(params.fast_period, 30)}_${asInteger(params.slow_period, 60)}`
        )
      ];
    case "laguerre_rsi":
      return [outputOrParam(params, "output_col", "laguerre_rsi")];
    case "frama": {
      const framaWindow = asInteger(params.window, 16);
      const outputCol = outputOrParam(params, "output_col", `frama_${framaWindow}`);
      return [
        outputCol,
        ...(asBoolean(params.add_diagnostics, false)
          ? [
              outputOrParam(params, "alpha_col", `${outputCol}_alpha`),
              outputOrParam(params, "fractal_dimension_col", `${outputCol}_fractal_dimension`)
            ]
          : [])
      ];
    }
    case "center_of_gravity":
      return [outputOrParam(params, "output_col", `center_of_gravity_${window}`)];
    case "even_better_sinewave":
      return [outputOrParam(params, "output_col", "even_better_sinewave")];
    case "autocorrelation_periodogram": {
      const minPeriod = asInteger(params.min_period, 10);
      const maxPeriod = asInteger(params.max_period, 48);
      const outputCol = outputOrParam(params, "output_col", `autocorrelation_periodogram_${minPeriod}_${maxPeriod}`);
      return [
        outputCol,
        ...(asBoolean(params.add_power, false)
          ? [outputOrParam(params, "power_col", `${outputCol}_power`)]
          : [])
      ];
    }
    case "homodyne_discriminator":
      return [outputOrParam(params, "output_col", "homodyne_discriminator")];
    case "hmm_regime": {
      const outputCol = outputOrParam(params, "output_col", "hmm_regime");
      return asBoolean(params.include_probabilities, false)
        ? [outputCol, ...Array.from({ length: asInteger(params.n_states, 2) }, (_, index) => `${asString(params.probability_prefix, "hmm_regime_prob")}_${index}`)]
        : [outputCol];
    }
    case "parkinson_volatility":
      return [outputOrParam(params, "output_col", `parkinson_vol_${window}`)];
    case "garman_klass_volatility":
      return [outputOrParam(params, "output_col", `garman_klass_vol_${window}`)];
    case "yang_zhang_volatility":
      return [outputOrParam(params, "output_col", `yang_zhang_vol_${window}`)];
    case "hurst_exponent":
      return [outputOrParam(params, "output_col", `hurst_${asInteger(params.window, 128)}`)];
    case "fractal_dimension":
      return [outputOrParam(params, "output_col", `fractal_dimension_${asInteger(params.window, 128)}`)];
    case "rate_of_change":
      return [outputOrParam(params, "output_col", `roc_${asInteger(params.window, 10)}`)];
    case "zscore_momentum":
      return [outputOrParam(params, "output_col", `zscore_momentum_${window}`)];
    case "rolling_r2_trend_quality": {
      const r2Window = asInteger(params.window, 96);
      const r2Base = `rolling_r2_trend_quality_${r2Window}`;
      return [
        outputOrParam(params, "output_col", r2Base),
        outputOrParam(params, "slope_col", `rolling_r2_slope_${r2Window}`),
        outputOrParam(params, "intercept_col", `rolling_r2_intercept_${r2Window}`),
        outputOrParam(params, "rising_col", `${r2Base}_rising`),
        outputOrParam(params, "trend_quality_col", `${r2Base}_ok`)
      ];
    }
    case "trend_slope_volatility": {
      const slopeWindow = asInteger(params.window, 96);
      const ratioBase = `trend_slope_vol_ratio_${slopeWindow}`;
      return [
        outputOrParam(params, "slope_col", `trend_slope_${slopeWindow}`),
        outputOrParam(params, "volatility_used_col", `trend_slope_volatility_used_${slopeWindow}`),
        outputOrParam(params, "slope_vol_ratio_col", ratioBase),
        outputOrParam(params, "positive_col", `${ratioBase}_positive`),
        outputOrParam(params, "rising_col", `${ratioBase}_rising`),
        outputOrParam(params, "strong_trend_col", `${ratioBase}_strong`)
      ];
    }
    case "volatility_of_volatility": {
      const volatilityCol = asString(params.volatility_col, "atr_over_price_20");
      const vovWindow = asInteger(params.window, 96);
      const meanWindow = optionalInteger(params.mean_window);
      const vovBase = `volatility_of_volatility_${volatilityCol}_${vovWindow}`;
      return [
        outputOrParam(params, "output_col", vovBase),
        ...(meanWindow !== null && meanWindow >= 2
          ? [
              outputOrParam(params, "mean_col", `${vovBase}_mean_${meanWindow}`),
              outputOrParam(params, "ratio_col", `${vovBase}_ratio_${meanWindow}`)
            ]
          : []),
        outputOrParam(params, "rising_col", `${vovBase}_rising`),
        outputOrParam(params, "high_vov_col", `${vovBase}_high`)
      ];
    }
    case "volatility_regime":
      return [outputOrParam(params, "output_col", "volatility_regime")];
    case "hilbert_transform": {
      const hilbertWindow = asInteger(params.window, 64);
      return [
        outputOrParam(params, "amplitude_col", `hilbert_amplitude_${hilbertWindow}`),
        outputOrParam(params, "phase_col", `hilbert_phase_${hilbertWindow}`),
        outputOrParam(params, "instantaneous_frequency_col", `hilbert_instantaneous_frequency_${hilbertWindow}`)
      ];
    }
    case "roofing_filter":
      return [outputOrParam(params, "output_col", `roofing_filter_${asInteger(params.high_pass_period, 48)}_${asInteger(params.low_pass_period, 10)}`)];
    case "supersmoother":
      return [outputOrParam(params, "output_col", `supersmoother_${asInteger(params.period, 10)}`)];
    case "shannon_entropy":
      return [outputOrParam(params, "output_col", `shannon_entropy_${asInteger(params.window, 64)}`)];
    case "permutation_entropy":
      return [outputOrParam(params, "output_col", `permutation_entropy_${asInteger(params.window, 64)}`)];
    case "vpin":
      return [outputOrParam(params, "output_col", `vpin_${asInteger(params.window, 50)}`)];
    case "order_flow_imbalance": {
      const ofiWindow = asInteger(params.window, 1);
      return [outputOrParam(params, "output_col", ofiWindow === 1 ? "order_flow_imbalance" : `order_flow_imbalance_${ofiWindow}`)];
    }
    default:
      return [];
  }
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

interface FeatureTransformsEditorProps {
  transforms: FeatureTransformConfig[];
  sourceColumns?: string[];
  restrictToSourceColumns?: boolean;
  applyToAllSourceColumns?: boolean;
  onChange: (transforms: FeatureTransformConfig[]) => void;
}

function FeatureTransformsEditor({
  transforms,
  sourceColumns = [],
  restrictToSourceColumns = false,
  applyToAllSourceColumns = false,
  onChange
}: FeatureTransformsEditorProps) {
  const sourceColumnOptions = uniqueStrings(sourceColumns);
  const transformKindOptions = applyToAllSourceColumns ? NESTED_TRANSFORM_KIND_OPTIONS : TRANSFORM_KIND_OPTIONS;
  const selectSourceValue = (value: unknown, fallbackIndex = 0): string => {
    const current = stringValue(value);
    if (!restrictToSourceColumns) {
      return current;
    }
    if (current && sourceColumnOptions.includes(current)) {
      return current;
    }
    return sourceColumnOptions[fallbackIndex] ?? "";
  };

  const updateTransform = (index: number, patch: FeatureTransformConfig) => {
    onChange(transforms.map((transform, idx) => (idx === index ? { ...transform, ...patch } : transform)));
  };

  const replaceKind = (index: number, kind: string) => {
    const previous = transforms[index] ?? {};
    const sourceCol = selectSourceValue(previous.source_col ?? previous.numerator_col, 0);
    const denominatorCol = selectSourceValue(previous.denominator_col, 1) || sourceCol;
    onChange(
      transforms.map((transform, idx) =>
        idx === index
          ? applyToAllSourceColumns
            ? defaultBulkFeatureTransform(kind)
            : defaultFeatureTransform(kind, sourceCol || preferredSourceColumn(sourceColumnOptions), denominatorCol)
          : transform
      )
    );
  };

  const addTransform = () => {
    onChange([
      ...transforms,
      applyToAllSourceColumns
        ? defaultBulkFeatureTransform()
        : defaultFeatureTransform("rolling_stat", preferredSourceColumn(sourceColumnOptions), secondarySourceColumn(sourceColumnOptions))
    ]);
  };

  const removeTransform = (index: number) => {
    const next = transforms.filter((_, idx) => idx !== index);
    onChange(
      next.length > 0
        ? next
        : [
            applyToAllSourceColumns
              ? defaultBulkFeatureTransform()
              : defaultFeatureTransform("rolling_stat", preferredSourceColumn(sourceColumnOptions), secondarySourceColumn(sourceColumnOptions))
          ]
    );
  };

  const sourceField = (
    transformIndex: number,
    transform: FeatureTransformConfig,
    field: "source_col" | "numerator_col" | "denominator_col",
    label: string,
    fallbackIndex = 0
  ) => {
    const value = selectSourceValue(transform[field], fallbackIndex);
    if (restrictToSourceColumns) {
      return (
        <label className="field">
          <span>{label}</span>
          <select
            value={value}
            disabled={sourceColumnOptions.length === 0}
            onChange={(event) => {
              const nextValue = event.target.value;
              const kind = stringValue(transform.kind, "rolling_stat");
              const patch: FeatureTransformConfig = { [field]: nextValue };
              if (kind === "ratio") {
                const numerator = field === "numerator_col" ? nextValue : stringValue(transform.numerator_col);
                const denominator = field === "denominator_col" ? nextValue : stringValue(transform.denominator_col);
                patch.output_col = numerator && denominator ? `${numerator}_over_${denominator}` : "";
              } else if (kind === "tsfresh_rolling") {
                patch.output_prefix = nextValue;
              } else if (field === "source_col") {
                patch.output_col = transformOutputCol(kind, nextValue, stringValue(transform.mode, "root_mean_square"));
              }
              updateTransform(transformIndex, patch);
            }}
          >
            {sourceColumnOptions.length === 0 ? <option value="">No feature outputs</option> : null}
            {sourceColumnOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
      );
    }
    return (
      <label className="field">
        <span>{label}</span>
        <input value={stringValue(transform[field])} onChange={(event) => updateTransform(transformIndex, { [field]: event.target.value })} />
      </label>
    );
  };

  return (
    <div className="transform-editor">
      {transforms.map((transform, transformIndex) => {
        const kind = stringValue(transform.kind, "rolling_stat");
        return (
          <div className="transform-row" key={`transform-${transformIndex}`}>
            <div className="step-card-header">
              <label className="field transform-kind-field">
                <span>transform kind</span>
                <select value={kind} onChange={(event) => replaceKind(transformIndex, event.target.value)}>
                  {transformKindOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <button className="icon-button" type="button" onClick={() => removeTransform(transformIndex)} title="Remove transform">
                x
              </button>
            </div>

            {kind === "ratio" ? (
              <div className="param-grid">
                {sourceField(transformIndex, transform, "numerator_col", "numerator_col", 0)}
                {sourceField(transformIndex, transform, "denominator_col", "denominator_col", 1)}
                <label className="field">
                  <span>output_col</span>
                  <input value={stringValue(transform.output_col)} onChange={(event) => updateTransform(transformIndex, { output_col: event.target.value })} />
                </label>
                <label className="field">
                  <span>eps</span>
                  <input type="number" value={numericInputValue(transform.eps)} onChange={(event) => updateTransform(transformIndex, { eps: parseNumericInput(event.target.value) })} />
                </label>
              </div>
            ) : (
              <div className="param-grid">
                {applyToAllSourceColumns ? null : sourceField(transformIndex, transform, "source_col", "source_col")}

                {kind === "rolling_stat" ? (
                  <label className="field">
                    <span>mode</span>
                    <select
                      value={stringValue(transform.mode, "root_mean_square")}
                      onChange={(event) =>
                        updateTransform(transformIndex, {
                          mode: event.target.value,
                          ...(applyToAllSourceColumns
                            ? {}
                            : { output_col: transformOutputCol("rolling_stat", selectSourceValue(transform.source_col), event.target.value) })
                        })
                      }
                    >
                      {ROLLING_STAT_MODE_OPTIONS.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}

                {kind === "tsfresh_rolling" ? (
                  <>
                    {applyToAllSourceColumns ? null : (
                      <label className="field">
                        <span>output_prefix</span>
                        <input value={stringValue(transform.output_prefix)} onChange={(event) => updateTransform(transformIndex, { output_prefix: event.target.value })} />
                      </label>
                    )}
                    <label className="field">
                      <span>calculators</span>
                      <textarea
                        defaultValue={formatValue(transform.calculators ?? ["root_mean_square"])}
                        rows={2}
                        onBlur={(event) => updateTransform(transformIndex, { calculators: parseListValue(event.target.value) })}
                      />
                    </label>
                  </>
                ) : applyToAllSourceColumns ? null : (
                  <label className="field">
                    <span>output_col</span>
                    <input value={stringValue(transform.output_col)} onChange={(event) => updateTransform(transformIndex, { output_col: event.target.value })} />
                  </label>
                )}

                <label className="field">
                  <span>window</span>
                  <input type="number" value={numericInputValue(transform.window)} onChange={(event) => updateTransform(transformIndex, { window: parseNumericInput(event.target.value, true) })} />
                </label>
                <label className="field">
                  <span>shift</span>
                  <input type="number" value={numericInputValue(transform.shift)} onChange={(event) => updateTransform(transformIndex, { shift: parseNumericInput(event.target.value, true) })} />
                </label>

                {kind === "rolling_clip" ? (
                  <>
                    <label className="field">
                      <span>lower_q</span>
                      <input type="number" step="0.01" value={numericInputValue(transform.lower_q)} onChange={(event) => updateTransform(transformIndex, { lower_q: parseNumericInput(event.target.value) })} />
                    </label>
                    <label className="field">
                      <span>upper_q</span>
                      <input type="number" step="0.01" value={numericInputValue(transform.upper_q)} onChange={(event) => updateTransform(transformIndex, { upper_q: parseNumericInput(event.target.value) })} />
                    </label>
                  </>
                ) : null}
              </div>
            )}
          </div>
        );
      })}
      <button className="secondary-button full-button" type="button" onClick={addTransform}>
        Add transform
      </button>
    </div>
  );
}

export function BuilderConfigurator({ title, sourceType, builders, steps, onChange }: BuilderConfiguratorProps) {
  const [selectedBuilder, setSelectedBuilder] = useState("");
  const builderByName = useMemo(() => new Map(builders.map((builder) => [builder.name, builder])), [builders]);
  const selectableBuilders = useMemo(() => builders, [builders]);
  const selectableBuilder = selectedBuilder || selectableBuilders[0]?.name || "";

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

  const updateParams = (index: number, params: Record<string, unknown>) => {
    updateStep(index, { params });
  };

  const setNestedTransformsEnabled = (index: number, enabled: boolean) => {
    const step = steps[index];
    if (!enabled) {
      const { transforms: _transforms, ...remainingParams } = step.params;
      updateParams(index, remainingParams);
      return;
    }
    updateParam(index, "transforms", bulkFeatureTransformsFromParams(step.params));
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
            {selectableBuilders.map((builder) => (
              <option key={builder.name} value={builder.name}>
                {builderDisplayName(builder)}
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
          const nestedSourceColumns = sourceType === "feature" ? deriveFeatureOutputColumns(step.step, step.params) : [];
          const estimatedOutputs = sourceType === "feature" ? nestedSourceColumns : [];
          const canUseNestedTransforms = sourceType === "feature" && step.step !== "feature_transforms";
          const nestedTransformsEnabled = Array.isArray(step.params.transforms);
          return (
            <div className="step-card" key={`${step.step}-${index}`}>
              <div className="step-card-header">
                <label className="check-row compact-check">
                  <input
                    type="checkbox"
                    checked={step.enabled}
                    onChange={(event) => updateStep(index, { enabled: event.target.checked })}
                  />
                  <span>{builderDisplayName(builder) || step.step}</span>
                </label>
                <button className="icon-button" type="button" onClick={() => removeStep(index)} title="Remove step">
                  x
                </button>
              </div>
              {builder?.description || builder?.docstring ? (
                <p className="builder-doc">{builder.description || builder.docstring?.split("\n")[0]}</p>
              ) : null}
              {estimatedOutputs.length > 0 ? (
                <div className="step-output-preview">
                  <span>estimated outputs</span>
                  <small>{compactColumnList(estimatedOutputs)}</small>
                </div>
              ) : null}
              {step.step === "feature_transforms" ? (
                <FeatureTransformsEditor
                  transforms={featureTransformsFromParams(step.params)}
                  onChange={(transforms) => updateParam(index, "transforms", transforms)}
                />
              ) : (
                <div className="param-grid">
                  {(builder?.parameters ?? []).map((parameter) => (
                    <div key={parameter.name}>
                      {parameterInput(parameter, step.params[parameter.name], (value) => updateParam(index, parameter.name, value))}
                    </div>
                  ))}
                </div>
              )}
              {canUseNestedTransforms ? (
                <div className="nested-transform-panel">
                  <label className="check-row compact-check">
                    <input
                      type="checkbox"
                      checked={nestedTransformsEnabled}
                      disabled={nestedSourceColumns.length === 0}
                      onChange={(event) => setNestedTransformsEnabled(index, event.target.checked)}
                    />
                    <span>transforms</span>
                  </label>
                  {nestedTransformsEnabled ? (
                    <FeatureTransformsEditor
                      transforms={bulkFeatureTransformsFromParams(step.params)}
                      sourceColumns={nestedSourceColumns}
                      restrictToSourceColumns
                      applyToAllSourceColumns
                      onChange={(transforms) => updateParam(index, "transforms", transforms)}
                    />
                  ) : null}
                </div>
              ) : null}
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
