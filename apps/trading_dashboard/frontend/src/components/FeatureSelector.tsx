import { useMemo, useState } from "react";
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
  const [query, setQuery] = useState("");
  const selectedSet = new Set(selected);
  const groups = useMemo(() => grouped(catalog), [catalog]);
  const normalizedQuery = query.trim().toLowerCase();
  const filteredGroups = useMemo(
    () =>
      groups
        .map(([group, items]) => [
          group,
          normalizedQuery
            ? items.filter((item) => {
                const haystack = `${group} ${item.name} ${item.dtype} ${item.category}`.toLowerCase();
                return haystack.includes(normalizedQuery);
              })
            : items
        ] as [string, CatalogItem[]])
        .filter(([, items]) => items.length > 0),
    [groups, normalizedQuery]
  );
  const visibleNames = useMemo(
    () => filteredGroups.flatMap(([, items]) => items.map((item) => item.name)),
    [filteredGroups]
  );
  const totalCount = groups.reduce((count, [, items]) => count + items.length, 0);
  const toggle = (name: string) => {
    const next = selectedSet.has(name)
      ? selected.filter((item) => item !== name)
      : [...selected, name];
    onChange(next);
  };
  const selectVisible = () => {
    onChange(Array.from(new Set([...selected, ...visibleNames])));
  };
  const clearVisible = () => {
    const visibleSet = new Set(visibleNames);
    onChange(selected.filter((name) => !visibleSet.has(name)));
  };

  return (
    <section className="control-section">
      <div className="section-heading-row">
        <h2>{title}</h2>
        <span>{selected.length}/{totalCount}</span>
      </div>
      <div className="selector-toolbar">
        <label className="field selector-search-field">
          <span>Search</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="name, dtype, group" />
        </label>
        <div className="selector-actions">
          <button className="secondary-button compact-button" type="button" disabled={visibleNames.length === 0} onClick={selectVisible}>
            Select
          </button>
          <button className="secondary-button compact-button" type="button" disabled={selected.length === 0} onClick={clearVisible}>
            Clear
          </button>
        </div>
      </div>
      <div className="selector-list">
        {filteredGroups.length === 0 ? <p className="empty-copy">No matches.</p> : null}
        {filteredGroups.map(([group, items]) => (
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
