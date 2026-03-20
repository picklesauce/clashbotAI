from dataclasses import dataclass


@dataclass
class Detection:
    class_name: str
    confidence: float
    bbox: tuple[int, int, int, int]


@dataclass
class GameState:
    troops_available: list[str]
    loot_gold: int
    loot_elixir: int
    current_state: str


@dataclass
class Action:
    type: str
    x: int
    y: int
    delay_ms: int
    x2: int | None = None
    y2: int | None = None
    duration_ms: int = 300
