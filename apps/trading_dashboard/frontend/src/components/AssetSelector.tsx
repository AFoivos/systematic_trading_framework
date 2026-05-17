import type { AssetSummary } from "../types/market";

interface AssetSelectorProps {
  assets: AssetSummary[];
  value: string;
  onChange: (value: string) => void;
}

export function AssetSelector({ assets, value, onChange }: AssetSelectorProps) {
  return (
    <label className="field">
      <span>Asset</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {assets.map((asset) => (
          <option key={asset.symbol} value={asset.symbol}>
            {asset.symbol}
          </option>
        ))}
      </select>
    </label>
  );
}

