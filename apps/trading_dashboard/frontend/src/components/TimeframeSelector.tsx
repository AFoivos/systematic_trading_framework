interface TimeframeSelectorProps {
  timeframes: string[];
  value: string;
  onChange: (value: string) => void;
}

export function TimeframeSelector({ timeframes, value, onChange }: TimeframeSelectorProps) {
  return (
    <label className="field">
      <span>Timeframe</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {timeframes.map((timeframe) => (
          <option key={timeframe} value={timeframe}>
            {timeframe}
          </option>
        ))}
      </select>
    </label>
  );
}

