from enum import Enum, auto
from typing import Any

from models import Action, Detection


class BotState(Enum):
    IDLE = auto()
    SEARCHING = auto()
    ATTACKING = auto()
    COLLECTING = auto()


class StateMachine:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.thresholds = config.get("thresholds", {})
        self.coordinates = config.get("coordinates", {})
        self.search_cfg = config.get("search", {})
        self._state = BotState.IDLE
        self._find_match_queued = True
        self._deployment_done = False
        self._skip_count = 0
        # Wall upgrades are only evaluated after a completed battle cycle.
        self._allow_wall_upgrade_check = False
        self._on_enter_idle()

    @property
    def state(self) -> BotState:
        return self._state

    @state.setter
    def state(self, new_state: BotState) -> None:
        if new_state == self._state:
            return
        self._state = new_state
        enter_hook = getattr(self, f"_on_enter_{new_state.name.lower()}", None)
        if enter_hook is not None:
            enter_hook()

    def tick(self, detections: list[Detection], ocr_data: dict) -> list[Action]:
        handler = {
            BotState.IDLE: self._tick_idle,
            BotState.SEARCHING: self._tick_searching,
            BotState.ATTACKING: self._tick_attacking,
            BotState.COLLECTING: self._tick_collecting,
        }[self._state]
        return handler(detections, ocr_data)

    # -- enter hooks (called once per transition) --

    def _on_enter_idle(self) -> None:
        self._find_match_queued = True

    def _on_enter_searching(self) -> None:
        self._find_match_queued = True
        self._skip_count = 0

    def _on_enter_attacking(self) -> None:
        self._deployment_done = False

    def _on_enter_collecting(self) -> None:
        # Returning home from battle arms one wall-upgrade evaluation.
        self._allow_wall_upgrade_check = True

    # -- tick handlers --

    def _tick_idle(self, detections: list[Detection], ocr_data: dict) -> list[Action]:
        actions: list[Action] = []
        home_gold = int(ocr_data.get("home_gold", 0))
        home_elixir = int(ocr_data.get("home_elixir", 0))
        template_hits = ocr_data.get("template_hits", {})
        wall_upgrade_min = int(self.thresholds.get("upgrade_min_resource", 10_000_000))
        home_resource_high = "home_resource_high" in template_hits

        if self._allow_wall_upgrade_check:
            self._allow_wall_upgrade_check = False
            if home_resource_high or home_gold >= wall_upgrade_min or home_elixir >= wall_upgrade_min:
                actions.extend(self._wall_upgrade_actions(detections, ocr_data))
                if actions:
                    return actions

        attack_xy = self._xy_from_detection_or_config(
            detections,
            ocr_data,
            "attack_button",
            "attack_button",
        )
        if attack_xy:
            x, y = attack_xy
            self.state = BotState.SEARCHING
            actions.append(Action(type="tap", x=x, y=y, delay_ms=900))
        return actions

    def _tick_searching(self, detections: list[Detection], ocr_data: dict) -> list[Action]:
        if self._find_match_queued:
            find_match_xy = self._xy_from_detection_or_config(
                detections,
                ocr_data,
                "find_match_button",
                "find_match_button",
            )
            if not find_match_xy:
                find_match_xy = self._xy_from_detection_or_config(
                    detections,
                    ocr_data,
                    "army_attack_button",
                    "army_attack_button",
                )
            if find_match_xy:
                x, y = find_match_xy
                self._find_match_queued = False
                return [Action(type="tap", x=x, y=y, delay_ms=1500)]
            # Keep trying until we actually locate the Find a Match button.
            return []

        enemy_gold = int(ocr_data.get("enemy_gold", 0))
        enemy_elixir = int(ocr_data.get("enemy_elixir", 0))
        template_hits = ocr_data.get("template_hits", {})
        min_gold = int(self.thresholds.get("match_min_gold", 1_000_000))
        min_elixir = int(self.thresholds.get("match_min_elixir", 1_000_000))
        max_skips_before_attack = int(self.search_cfg.get("max_skips_before_attack", 6))
        enemy_loot_ready = "enemy_loot_ready" in template_hits
        loot_ready_by_ocr = enemy_gold >= min_gold and enemy_elixir >= min_elixir

        if enemy_loot_ready or loot_ready_by_ocr:
            self.state = BotState.ATTACKING
            return []
        if self._skip_count >= max_skips_before_attack:
            self.state = BotState.ATTACKING
            return []

        next_xy = self._xy_from_detection_or_config(
            detections,
            ocr_data,
            "next_match_button",
            "next_match_button",
        )
        if next_xy:
            x, y = next_xy
            self._skip_count += 1
            return [Action(type="tap", x=x, y=y, delay_ms=1200)]
        return []

    def _tick_attacking(self, detections: list[Detection], ocr_data: dict) -> list[Action]:
        if not self._deployment_done:
            self._deployment_done = True
            return self._build_deploy_actions(ocr_data)

        return_home_xy = self._xy_from_detection_or_config(
            detections,
            ocr_data,
            "return_home_button",
            "return_home_button",
        )
        if return_home_xy:
            x, y = return_home_xy
            self.state = BotState.COLLECTING
            return [Action(type="tap", x=x, y=y, delay_ms=1800)]
        return []

    def _tick_collecting(self, detections: list[Detection], ocr_data: dict) -> list[Action]:
        self.state = BotState.IDLE
        return []

    def _wall_upgrade_actions(self, detections: list[Detection], sensor_data: dict[str, Any]) -> list[Action]:
        wall_xy = self._xy_from_detection_or_config(
            detections,
            sensor_data,
            "wall",
            "wall_sample",
            allow_config_fallback=False,
        )
        upgrade_xy = self._xy_from_detection_or_config(
            detections,
            sensor_data,
            "upgrade_button",
            "wall_upgrade_button",
            allow_config_fallback=False,
        )
        if not upgrade_xy:
            upgrade_xy = self._xy_from_detection_or_config(
                detections,
                sensor_data,
                "upgrade_button",
                "wall_upgrade_button_alt",
                allow_config_fallback=False,
            )
        if not wall_xy or not upgrade_xy:
            return []

        wall_x, wall_y = wall_xy
        up_x, up_y = upgrade_xy
        return [
            Action(type="tap", x=wall_x, y=wall_y, delay_ms=350),
            Action(type="tap", x=up_x, y=up_y, delay_ms=650),
        ]

    def _build_deploy_actions(self, sensor_data: dict[str, Any]) -> list[Action]:
        deploy_points = self.coordinates.get("deploy_points", {})
        dragons = deploy_points.get("dragons", [])
        balloons = deploy_points.get("balloons", [])
        heroes = deploy_points.get("heroes", [])
        template_hits = sensor_data.get("template_hits", {})

        actions: list[Action] = []
        dragon_slot = template_hits.get("dragon_slot")
        dragon_duke_slot = template_hits.get("dragon_duke")
        balloon_slot = template_hits.get("balloon_slot")
        if isinstance(dragon_slot, tuple) and len(dragon_slot) >= 2:
            actions.append(Action(type="tap", x=int(dragon_slot[0]), y=int(dragon_slot[1]), delay_ms=120))
        if isinstance(dragon_duke_slot, tuple) and len(dragon_duke_slot) >= 2:
            actions.append(Action(type="tap", x=int(dragon_duke_slot[0]), y=int(dragon_duke_slot[1]), delay_ms=120))
        if isinstance(balloon_slot, tuple) and len(balloon_slot) >= 2:
            actions.append(Action(type="tap", x=int(balloon_slot[0]), y=int(balloon_slot[1]), delay_ms=120))

        actions.extend(self._repeat_taps(dragons, total_count=13, delay_ms=120))
        actions.extend(self._repeat_taps(balloons, total_count=16, delay_ms=120))

        for hero_name in (
            "king",
            "queen",
            "archer_queen",
            "grand_warden",
            "royal_champion",
            "minion_prince",
        ):
            hero_hit = template_hits.get(hero_name)
            if isinstance(hero_hit, tuple) and len(hero_hit) >= 2:
                actions.append(Action(type="tap", x=int(hero_hit[0]), y=int(hero_hit[1]), delay_ms=180))

        actions.extend(self._repeat_taps(heroes, total_count=len(heroes), delay_ms=180))
        return actions

    def _repeat_taps(self, points: list[Any], total_count: int, delay_ms: int) -> list[Action]:
        if not points or total_count <= 0:
            return []

        actions: list[Action] = []
        for index in range(total_count):
            point = points[index % len(points)]
            if not isinstance(point, list) or len(point) != 2:
                continue
            x = int(point[0])
            y = int(point[1])
            actions.append(Action(type="tap", x=x, y=y, delay_ms=delay_ms))
        return actions

    def _xy_from_detection_or_config(
        self,
        detections: list[Detection],
        sensor_data: dict[str, Any],
        detection_name: str,
        config_key: str,
        allow_config_fallback: bool = True,
    ) -> tuple[int, int] | None:
        for detection in detections:
            if detection.class_name != detection_name:
                continue
            x1, y1, x2, y2 = detection.bbox
            return ((x1 + x2) // 2, (y1 + y2) // 2)

        template_hits = sensor_data.get("template_hits", {})
        template_hit = template_hits.get(config_key)
        if isinstance(template_hit, tuple) and len(template_hit) >= 2:
            return (int(template_hit[0]), int(template_hit[1]))
        if isinstance(template_hit, list) and len(template_hit) >= 2:
            return (int(template_hit[0]), int(template_hit[1]))

        if allow_config_fallback:
            point = self.coordinates.get(config_key)
            if isinstance(point, list) and len(point) == 2:
                return (int(point[0]), int(point[1]))
        return None
