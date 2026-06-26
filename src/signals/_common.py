from __future__ import annotations


ALLOWED_DIRECTIONAL_MODES = frozenset(
    {"long_only", "short_only", "long_short", "long_short_hold"}
)


def resolve_signal_output_name(
    *,
    signal_col: str | None,
    default: str,
) -> str:
    """
    Apply the registered ``resolve_signal_output_name`` signal transformation.
    
    This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        signals:
          kind: resolve_signal_output_name
          params:
            signal_col: <required>
            default: <required>
          output_cols:
            - configured by signal_col
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    signal_col:
        Output dataframe column configured by ``signal_col``.
    default:
        Configuration parameter accepted by this signal.
    """
    return str(signal_col or default)


__all__ = [
    "ALLOWED_DIRECTIONAL_MODES",
    "resolve_signal_output_name",
]
