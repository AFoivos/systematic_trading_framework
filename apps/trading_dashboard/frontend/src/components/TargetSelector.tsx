import type { CatalogItem } from "../types/market";
import { FeatureSelector } from "./FeatureSelector";

interface TargetSelectorProps {
  targets: CatalogItem[];
  selected: string[];
  onChange: (selected: string[]) => void;
}

export function TargetSelector(props: TargetSelectorProps) {
  return <FeatureSelector title="Targets" catalog={props.targets} selected={props.selected} onChange={props.onChange} />;
}

