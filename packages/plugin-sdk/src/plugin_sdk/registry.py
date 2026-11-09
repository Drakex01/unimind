"""Domain Plugin Registry and Manifest Validator."""

import logging
from pathlib import Path
from typing import Dict, List, Optional
import yaml
from pydantic import ValidationError
from .manifest import PluginManifest

logger = logging.getLogger("unimind.plugin_registry")


class PluginLoadError(Exception):
    """Raised when a plugin manifest is invalid or missing."""
    pass


class PluginRegistry:
    """Registry maintaining validated domain plugins loaded from declarative manifests."""

    def __init__(self):
        self._plugins: Dict[str, PluginManifest] = {}
        self._plugin_paths: Dict[str, Path] = {}
        self._plugin_instructions: Dict[str, str] = {}

    def register_manifest(self, manifest: PluginManifest, plugin_dir: Optional[Path] = None, instructions_text: str = "") -> None:
        plugin_id = manifest.plugin.id
        self._plugins[plugin_id] = manifest
        if plugin_dir:
            self._plugin_paths[plugin_id] = plugin_dir
        self._plugin_instructions[plugin_id] = instructions_text
        logger.info(f"Loaded plugin: {plugin_id} v{manifest.plugin.version}")

    def load_from_directory(self, plugin_dir: Path) -> PluginManifest:
        """Load and strictly validate a single plugin folder containing plugin.yaml."""
        manifest_path = plugin_dir / "plugin.yaml"
        if not manifest_path.exists():
            raise PluginLoadError(f"Missing plugin.yaml in directory: {plugin_dir}")

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            raise PluginLoadError(f"Failed to parse YAML in {manifest_path}: {e}") from e

        try:
            manifest = PluginManifest.model_validate(data)
        except ValidationError as ve:
            raise PluginLoadError(f"Schema validation failed for {manifest_path}:\n{ve}") from ve

        # Verify referenced instructions file if present
        inst_rel_path = manifest.instructions.path
        inst_full_path = plugin_dir / inst_rel_path
        instructions_text = ""
        if inst_full_path.exists():
            with open(inst_full_path, "r", encoding="utf-8") as f:
                instructions_text = f.read()

        self.register_manifest(manifest, plugin_dir, instructions_text)
        return manifest

    def discover_and_load(self, plugins_root: Path) -> List[PluginManifest]:
        """Scan a root directory for all plugin subdirectories."""
        if not plugins_root.exists() or not plugins_root.is_dir():
            logger.warning(f"Plugins root directory does not exist: {plugins_root}")
            return []

        loaded = []
        for item in plugins_root.iterdir():
            if item.is_dir() and (item / "plugin.yaml").exists():
                try:
                    manifest = self.load_from_directory(item)
                    loaded.append(manifest)
                except Exception as exc:
                    logger.error(f"Failed loading plugin at {item}: {exc}")
        return loaded

    def get_plugin(self, plugin_id: str) -> Optional[PluginManifest]:
        return self._plugins.get(plugin_id)

    def get_instructions(self, plugin_id: str) -> str:
        return self._plugin_instructions.get(plugin_id, "")

    def list_plugins(self) -> List[PluginManifest]:
        return list(self._plugins.values())
