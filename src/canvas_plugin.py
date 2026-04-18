"""Canvas plugin registry

Provide a minimal plugin registry for Canvas generation so the Canvas
implementation can be swapped or stubbed in tests. The existing
CanvasGenerator (src/canvas_generator.py) is registered as the default
plugin. Plugins may also be discovered via the `gedcom_to_markdown.canvas_plugins`
entry point group to allow third-party distribution.
"""

from typing import Type, Dict, Optional
import logging

logger = logging.getLogger(__name__)

_registry: Dict[str, Type] = {}


def register_canvas_plugin(name: str, cls: Type) -> None:
    """Register a canvas plugin class under a name."""
    _registry[name] = cls


def discover_entrypoint_plugins(
    group: str = "gedcom_to_markdown.canvas_plugins",
) -> None:
    """Discover and register plugins declared via entry points.

    Looks for entry points in the given group and registers each loaded
    object under its entry point name. Failures are logged but do not
    interrupt execution.
    """
    try:
        try:
            # Python 3.8+ importlib.metadata
            from importlib import metadata as importlib_metadata
        except Exception:
            import importlib_metadata  # type: ignore

        # `entry_points(group=...)` is supported in newer stdlib versions
        try:
            entries = importlib_metadata.entry_points(group=group)
        except TypeError:
            # Older return shape: call then filter
            entries = [
                ep
                for ep in importlib_metadata.entry_points()
                if getattr(ep, "group", None) == group
            ]

        for ep in entries:
            try:
                # Some importlib.metadata implementations may return different shapes
                # (EntryPoint objects, strings, or other types). Use getattr to be
                # defensive and avoid mypy/ty issues when attributes are missing.
                load_fn = getattr(ep, "load", None)
                name_attr = getattr(ep, "name", None)
                if callable(load_fn):
                    plugin_obj = load_fn()
                    plugin_name = name_attr or getattr(
                        plugin_obj, "__name__", "unknown"
                    )
                    register_canvas_plugin(plugin_name, plugin_obj)
                    logger.info(
                        f"Registered canvas plugin from entrypoint: {plugin_name}"
                    )
                else:
                    logger.debug("Skipping non-callable entry point: %r", ep)
            except Exception:
                logger.exception("Failed to load canvas plugin entry point: %r", ep)
    except Exception:
        # Discovery is best-effort; do not raise to avoid breaking runtime.
        logger.debug(
            "Canvas plugin discovery skipped (importlib.metadata unavailable or failed)"
        )


def get_canvas_plugin(name: Optional[str] = None) -> Type:
    """Return the registered canvas plugin class by name.

    If `name` is None, will attempt to discover entrypoint plugins and
    return the plugin registered as "default" (the bundled CanvasGenerator).
    """
    # Discover entrypoint plugins first (best-effort)
    discover_entrypoint_plugins()

    plugin_name = name or "default"

    if plugin_name in _registry:
        return _registry[plugin_name]

    if name is None or plugin_name == "default":
        # Lazy default registration: import the bundled CanvasGenerator
        try:
            # Prefer package-local import (when running as module)
            from canvas_generator import CanvasGenerator
        except Exception:
            # Fallback to package import path used by some test runners
            from src.canvas_generator import CanvasGenerator

        register_canvas_plugin("default", CanvasGenerator)
        return _registry.get(plugin_name, CanvasGenerator)

    available_plugins = ", ".join(sorted(_registry)) or "default"
    raise ValueError(
        f"Unknown canvas plugin: {plugin_name}. "
        f"Available plugins: {available_plugins}"
    )


def list_plugins() -> Dict[str, Type]:
    """Return a shallow copy of the plugin registry.

    Ensures the bundled default plugin is registered before returning so that
    callers (e.g. ``--list-canvas-plugins``) always see at least the default.
    """
    # Ensure discovered plugins are registered before listing
    discover_entrypoint_plugins()
    # Ensure at least the bundled default is present
    if "default" not in _registry:
        get_canvas_plugin(None)
    return dict(_registry)
