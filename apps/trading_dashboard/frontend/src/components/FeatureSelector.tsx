import type { CatalogItem, FeatureCatalog } from "../types/market";

interface FeatureSelectorProps {
  title: string;
  catalog: FeatureCatalog | CatalogItem[];
  selected: string[];
  onChange: (selected: string[]) => void;
}

function grouped(catalog: FeatureCatalog | CatalogItem[]): Array<[string, CatalogItem[]]> {
  if (Array.isArray(catalog)) {
    return [["available", catalog]];
  }
  return Object.entries(catalog).filter(([, items]) => items.length > 0);
}

export function FeatureSelector({ title, catalog, selected, onChange }: FeatureSelectorProps) {
  const selectedSet = new Set(selected);
  const toggle = (name: string) => {
    const next = selectedSet.has(name)
      ? selected.filter((item) => item !== name)
      : [...selected, name];
    onChange(next);
  };

  return (
    <section className="control-section">
      <h2>{title}</h2>
      <div className="selector-list">
        {grouped(catalog).map(([group, items]) => (
          <div className="selector-group" key={group}>
            <div className="selector-group-title">{group}</div>
            {items.map((item) => (
              <label className="check-row" key={`${group}-${item.name}`}>
                <input
                  type="checkbox"
                  checked={selectedSet.has(item.name)}
                  onChange={() => toggle(item.name)}
                />
                <span>{item.name}</span>
              </label>
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}

