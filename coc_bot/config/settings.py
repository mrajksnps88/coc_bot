"""Dataclass-based bot settings with sensible defaults."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ADBSettings:
    """Android Debug Bridge connection parameters."""
    server_host: str = "127.0.0.1"
    server_port: int = 5037
    device_address: str = "localhost:6520"
    adb_path: str | None = None
    connection_timeout: float = 10.0
    command_timeout: float = 5.0


@dataclass
class VisionSettings:
    """Template matching and image recognition parameters."""
    match_threshold: float = 0.80
    multi_scale_range: tuple[float, float, int] = (0.8, 1.2, 10)
    grayscale: bool = True
    nms_overlap_threshold: float = 0.3
    template_dir: Path = field(default_factory=lambda: Path("templates"))


@dataclass
class TimingSettings:
    """Timing and delay configuration for human-like behaviour."""
    capture_interval: float = 1.0
    action_delay_range: tuple[float, float] = (0.3, 0.8)
    idle_check_interval: float = 60.0
    state_change_cooldown: float = 2.0
    max_stuck_time: float = 30.0


@dataclass
class FarmingSettings:
    """Loot thresholds and attack session limits."""
    min_gold_loot: int = 200_000
    min_elixir_loot: int = 200_000
    min_dark_elixir_loot: int = 0
    max_search_time: float = 120.0
    max_attacks_per_session: int = 10
    attack_style: str = "snipe" # "snipe" or "spam"
    train_army_index: int = 0  # 0 for first army, 1 for second, etc.
    troop_slot_x: int | None = None
    troop_slot_y: int | None = None
    troop_slots: list[tuple[int, int]] = field(default_factory=list)
    hero_slots: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class AutoWallSettings:
    """Settings for automatic wall upgrading."""
    enabled: bool = False
    wall_x: int | None = None
    wall_y: int | None = None
    btn_gold_x: int | None = None
    btn_gold_y: int | None = None
    btn_elixir_x: int | None = None
    btn_elixir_y: int | None = None
    btn_confirm_x: int | None = None
    btn_confirm_y: int | None = None
    keep_gold: int = 2000000
    keep_elixir: int = 2000000
    upgrade_with: str = "both"  # "gold", "elixir", or "both"


@dataclass
class BotSettings:
    """Top-level bot configuration container."""
    adb: ADBSettings = field(default_factory=ADBSettings)
    vision: VisionSettings = field(default_factory=VisionSettings)
    timing: TimingSettings = field(default_factory=TimingSettings)
    farming: FarmingSettings = field(default_factory=FarmingSettings)
    auto_wall: AutoWallSettings = field(default_factory=AutoWallSettings)
    screen_regions: dict = field(default_factory=dict)
    dry_run: bool = False
    debug_screenshots: bool = False
    log_level: str = "INFO"
