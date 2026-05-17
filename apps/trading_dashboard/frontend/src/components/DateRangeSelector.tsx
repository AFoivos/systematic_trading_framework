interface DateRangeSelectorProps {
  start: string;
  end: string;
  onChange: (patch: { start?: string; end?: string }) => void;
}

export function DateRangeSelector({ start, end, onChange }: DateRangeSelectorProps) {
  return (
    <div className="field-grid two">
      <label className="field">
        <span>Start</span>
        <input type="date" value={start} onChange={(event) => onChange({ start: event.target.value })} />
      </label>
      <label className="field">
        <span>End</span>
        <input type="date" value={end} onChange={(event) => onChange({ end: event.target.value })} />
      </label>
    </div>
  );
}

