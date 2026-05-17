import type { CatalogItem } from "../types/market";
import { FeatureSelector } from "./FeatureSelector";

interface SignalSelectorProps {
  signals: CatalogItem[];
  selected: string[];
  onChange: (selected: string[]) => void;
}

export function SignalSelector(props: SignalSelectorProps) {
  return <FeatureSelector title="Signals" catalog={props.signals} selected={props.selected} onChange={props.onChange} />;
}

