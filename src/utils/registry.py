from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from types import MappingProxyType
from typing import TypeVar


T = TypeVar("T")


class RegistryLookupError(KeyError):
    """Raised when a requested config component name is not registered."""


class RegistryDefinitionError(ValueError):
    """Raised when a registry definition is internally inconsistent."""


def build_registry(
    category: str,
    entries: Iterable[tuple[str, T]],
) -> Mapping[str, T]:
    registry: dict[str, T] = {}
    duplicates: list[str] = []
    for raw_name, component in entries:
        name = str(raw_name).strip()
        if not name:
            raise RegistryDefinitionError(f"{category} registry contains an empty component name.")
        if name in registry:
            duplicates.append(name)
            continue
        registry[name] = component

    if duplicates:
        duplicate_list = ", ".join(sorted(set(duplicates)))
        raise RegistryDefinitionError(
            f"Duplicate {category} registry name(s): {duplicate_list}."
        )
    return MappingProxyType(registry)


def get_registered_component(
    registry: Mapping[str, T],
    name: str,
    *,
    category: str,
    aliases: Mapping[str, T] | None = None,
) -> T:
    resolved_name = str(name).strip()
    if resolved_name in registry:
        return registry[resolved_name]
    if aliases is not None and resolved_name in aliases:
        return aliases[resolved_name]

    available = sorted(set(registry) | set(aliases or {}))
    preview = ", ".join(available)
    raise RegistryLookupError(
        f"Unknown {category} '{resolved_name}'. Available {category} names: {preview}."
    )


def registry_names(registry: Mapping[str, object], *extra: Mapping[str, object]) -> frozenset[str]:
    names: set[str] = set(registry)
    for mapping in extra:
        names.update(mapping)
    return frozenset(names)


def lazy_callable(module_name: str, attr_name: str) -> Callable[..., object]:
    def _call(*args: object, **kwargs: object) -> object:
        from importlib import import_module

        module = import_module(module_name)
        return getattr(module, attr_name)(*args, **kwargs)

    _call.__name__ = attr_name
    _call.__qualname__ = attr_name
    _call.__module__ = module_name
    return _call


__all__ = [
    "RegistryDefinitionError",
    "RegistryLookupError",
    "build_registry",
    "get_registered_component",
    "lazy_callable",
    "registry_names",
]
