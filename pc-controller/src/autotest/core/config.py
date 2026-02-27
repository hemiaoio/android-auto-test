"""Configuration management using YAML files with .env support."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def load_dotenv() -> None:
    """加载 .env 文件中的环境变量。

    按优先级依次查找: 当前目录 → pc-controller 目录 → 项目根目录。
    已有的环境变量不会被覆盖。
    """
    try:
        from dotenv import load_dotenv as _load
    except ImportError:
        return

    cwd = Path.cwd()
    candidates = [
        cwd / ".env",
        cwd / "pc-controller" / ".env",
        cwd.parent / ".env",
    ]
    for env_file in candidates:
        if env_file.is_file():
            _load(env_file, override=False)
            break


@dataclass
class DeviceConfig:
    control_port: int = 18900
    binary_port: int = 18901
    event_port: int = 18902
    connect_timeout: float = 10.0
    command_timeout: float = 30.0
    heartbeat_interval: float = 5.0


@dataclass
class RunnerConfig:
    parallel: bool = False
    max_workers: int = 4
    retry_count: int = 0
    retry_delay: float = 1.0
    screenshot_on_failure: bool = True
    default_timeout: float = 30.0


@dataclass
class ReporterConfig:
    output_dir: str = "./reports"
    formats: list[str] = field(default_factory=lambda: ["html", "json"])
    include_screenshots: bool = True
    include_logs: bool = True


@dataclass
class OcrOnlineConfig:
    api_base: str = "https://api.deepseek.com/v1"
    api_key: str = "${AUTOTEST_OCR_API_KEY}"
    model: str = "deepseek-chat"
    timeout: float = 60.0


@dataclass
class OcrConfig:
    backend: str = "auto"  # auto / online / paddleocr / tesseract
    online: OcrOnlineConfig = field(default_factory=OcrOnlineConfig)
    paddleocr_lang: str = "ch"
    paddleocr_use_gpu: bool = False
    tesseract_lang: str = "chi_sim+eng"


@dataclass
class AutoTestConfig:
    device: DeviceConfig = field(default_factory=DeviceConfig)
    runner: RunnerConfig = field(default_factory=RunnerConfig)
    reporter: ReporterConfig = field(default_factory=ReporterConfig)
    ocr: OcrConfig = field(default_factory=OcrConfig)
    log_level: str = "INFO"
    plugins: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path) -> AutoTestConfig:
        """Load configuration from a YAML file.

        自动加载 .env 文件中的环境变量（如存在）。
        """
        load_dotenv()
        path = Path(path)
        if not path.exists():
            return cls()

        with open(path) as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}

        config = cls()
        if "device" in data:
            config.device = DeviceConfig(**data["device"])
        if "runner" in data:
            config.runner = RunnerConfig(**data["runner"])
        if "reporter" in data:
            config.reporter = ReporterConfig(**data["reporter"])
        if "ocr" in data:
            ocr_data = data["ocr"]
            ocr_cfg = OcrConfig()
            ocr_cfg.backend = ocr_data.get("backend", "auto")
            if "online" in ocr_data:
                ocr_cfg.online = OcrOnlineConfig(**ocr_data["online"])
            ocr_cfg.paddleocr_lang = ocr_data.get("paddleocr_lang", "ch")
            ocr_cfg.paddleocr_use_gpu = ocr_data.get("paddleocr_use_gpu", False)
            ocr_cfg.tesseract_lang = ocr_data.get("tesseract_lang", "chi_sim+eng")
            config.ocr = ocr_cfg
        config.log_level = data.get("log_level", "INFO")
        config.plugins = data.get("plugins", [])
        return config

    def save(self, path: str | Path) -> None:
        """Save configuration to a YAML file."""
        import dataclasses

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(dataclasses.asdict(self), f, default_flow_style=False)
