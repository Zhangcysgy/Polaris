"""配置加载器 —— 读取 polaris.yaml"""

from pathlib import Path
from typing import Any

import yaml


class Config:
    """Polaris 配置管理器。

    加载 polaris.yaml，提供按路径访问配置项的能力。
    """

    def __init__(self, config_path: str | Path = "polaris.yaml"):
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"配置文件未找到: {self.config_path.absolute()}\n"
                f"请确保在 Polaris 项目根目录运行命令。"
            )
        with open(self.config_path, "r", encoding="utf-8") as f:
            self._data: dict[str, Any] = yaml.safe_load(f)

    def get(self, *keys: str, default: Any = None) -> Any:
        """按路径读取配置，如 config.get("engine_one", "auto_capture")。"""
        node = self._data
        for key in keys:
            if isinstance(node, dict):
                node = node.get(key)
            else:
                return default
            if node is None:
                return default
        return node

    def __repr__(self) -> str:
        return f"Config({self.config_path})"


# 全局单例
_config: Config | None = None


def get_config(config_path: str | Path = "polaris.yaml") -> Config:
    """获取全局配置单例。"""
    global _config
    if _config is None:
        _config = Config(config_path)
    return _config
