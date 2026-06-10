import json
import os
from copy import deepcopy

from config import APP_DIR, SKINS_DIR, TEMPLATES_DIR, resource_path


DEFAULT_SKIN_ID = "classic"
UNLOCK_TIERS = {
    "easy": 30,
    "medium": 50,
    "hard": 100,
}
DEMO_UNLOCK_TIERS = {
    "easy": 1,
    "medium": 2,
    "hard": 3,
}
TIER_LABELS_BG = {
    "easy": "Лесен скин",
    "medium": "Среден скин",
    "hard": "Труден скин",
}
TIER_NAMES_BG = {
    "easy": "лесен",
    "medium": "среден",
    "hard": "труден",
}

DEFAULT_COLORS = {
    "bg": "#1e1e2f",
    "panel": "#2e2e4f",
    "text": "#ffffff",
    "muted": "#cfcfe6",
    "button": "#3e3e5e",
    "button_active": "#32bb5b",
    "button_hover": "#52527a",
    "accent": "#ffd54f",
    "success": "#4caf50",
    "danger": "#f44336",
    "warning": "#ffeb3b",
    "link": "#64b5f6",
    "option_idle": "#3e3e5e",
    "option_active": "#2e2e4f",
    "option_correct": "#2e7d32",
    "option_wrong": "#c62828",
    "option_neutral": "#424242",
}

BUILTIN_SKINS = [
    {
        "id": "classic",
        "name": "Classic Focus",
        "description": "The original calm quiz look.",
        "unlock": {},
        "colors": DEFAULT_COLORS,
    },
    {
        "id": "candy",
        "name": "Candy Pop",
        "description": "Bright, friendly colors for early wins.",
        "unlock": {"tier": "easy", "total_correct": 30},
        "colors": {
            "bg": "#2a1831",
            "panel": "#3a2445",
            "text": "#fff7fb",
            "muted": "#ffd3ea",
            "button": "#7c3f8f",
            "button_active": "#ff6fae",
            "button_hover": "#9652aa",
            "accent": "#ffe066",
            "success": "#55d68a",
            "danger": "#ff5c7a",
            "warning": "#ffe066",
            "link": "#8be9ff",
            "option_idle": "#6f377f",
            "option_active": "#4b2b58",
        },
    },
    {
        "id": "blocks",
        "name": "Block Builder",
        "description": "Playful block colors for steady progress.",
        "unlock": {"tier": "easy", "total_correct": 30},
        "colors": {
            "bg": "#14251c",
            "panel": "#1f3a2b",
            "text": "#f4fff8",
            "muted": "#b7dfc6",
            "button": "#2f7049",
            "button_active": "#e1b12c",
            "button_hover": "#3d8a5d",
            "accent": "#f6d365",
            "success": "#57c84d",
            "danger": "#d94f3d",
            "warning": "#ffcf4a",
            "link": "#7dcfff",
            "option_idle": "#2f7049",
            "option_active": "#284b38",
        },
    },
    {
        "id": "galaxy",
        "name": "Galaxy Run",
        "description": "Deep space contrast for stronger scores.",
        "unlock": {"tier": "medium", "total_correct": 50},
        "colors": {
            "bg": "#111827",
            "panel": "#1f2937",
            "text": "#f8fafc",
            "muted": "#cbd5e1",
            "button": "#374151",
            "button_active": "#06b6d4",
            "button_hover": "#4b5563",
            "accent": "#f59e0b",
            "success": "#22c55e",
            "danger": "#ef4444",
            "warning": "#facc15",
            "link": "#38bdf8",
            "option_idle": "#334155",
            "option_active": "#1e293b",
        },
    },
    {
        "id": "hero",
        "name": "Hero Web",
        "description": "High-energy red and blue for excellent results.",
        "unlock": {"tier": "medium", "total_correct": 50},
        "colors": {
            "bg": "#171923",
            "panel": "#252b3a",
            "text": "#ffffff",
            "muted": "#d7e3ff",
            "button": "#1d4ed8",
            "button_active": "#dc2626",
            "button_hover": "#2563eb",
            "accent": "#f8fafc",
            "success": "#16a34a",
            "danger": "#ef4444",
            "warning": "#fde047",
            "link": "#93c5fd",
            "option_idle": "#1e40af",
            "option_active": "#253858",
        },
    },
    {
        "id": "arena",
        "name": "Arena Neon",
        "description": "A competitive look for near-perfect runs.",
        "unlock": {"tier": "hard", "total_correct": 100},
        "colors": {
            "bg": "#101114",
            "panel": "#1f2128",
            "text": "#f8fafc",
            "muted": "#cfd7e6",
            "button": "#3f3f46",
            "button_active": "#f97316",
            "button_hover": "#52525b",
            "accent": "#22d3ee",
            "success": "#84cc16",
            "danger": "#ef4444",
            "warning": "#facc15",
            "link": "#67e8f9",
            "option_idle": "#34343b",
            "option_active": "#22252c",
        },
    },
]


class SkinManager:
    def __init__(self, skins_dir=SKINS_DIR):
        self.skins_dir = skins_dir
        self._skins = {}
        self._load_builtin_skins()
        self._load_custom_skins()
        self._load_template_skins()

    def _load_builtin_skins(self):
        for skin in BUILTIN_SKINS:
            normalized = self._normalize_skin(skin)
            self._skins[normalized["id"]] = normalized

    def _load_custom_skins(self):
        catalog_candidates = [
            os.path.join(self.skins_dir, "skins.json"),
            resource_path(os.path.join("skins", "skins.json")),
        ]
        catalog_path = next((path for path in catalog_candidates if os.path.exists(path)), None)
        if not catalog_path:
            return
        try:
            with open(catalog_path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except Exception:
            return
        raw_skins = payload.get("skins", payload) if isinstance(payload, dict) else payload
        if not isinstance(raw_skins, list):
            return
        for raw in raw_skins:
            if not isinstance(raw, dict):
                continue
            try:
                normalized = self._normalize_skin(raw)
                self._skins[normalized["id"]] = normalized
            except ValueError:
                continue

    def _load_template_skins(self):
        if not os.path.isdir(TEMPLATES_DIR):
            return
        templates_by_tier = {tier: [] for tier in UNLOCK_TIERS}
        for name in sorted(os.listdir(TEMPLATES_DIR), key=str.lower):
            folder = os.path.join(TEMPLATES_DIR, name)
            if not os.path.isdir(folder):
                continue
            tier = self._read_template_tier(folder)
            if tier in templates_by_tier:
                templates_by_tier[tier].append(folder)

        for tier, folders in templates_by_tier.items():
            for index, folder in enumerate(folders, start=1):
                skin_id = self._template_target_skin_id(tier, index)
                skin = self._skin_from_template(folder, tier, index, skin_id)
                self._skins[skin_id] = self._normalize_skin(skin)

    def _read_template_tier(self, folder):
        candidates = ["tier.txt", "skin.txt", "type.txt", "unlock.txt", "level.txt"]
        for filename in candidates:
            path = os.path.join(folder, filename)
            tier = self._read_tier_file(path)
            if tier:
                return tier
        for filename in sorted(os.listdir(folder), key=str.lower):
            if filename.lower().endswith(".txt"):
                tier = self._read_tier_file(os.path.join(folder, filename))
                if tier:
                    return tier
        return None

    def _read_tier_file(self, path):
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                value = fh.read().strip().lower()
        except Exception:
            return None
        return value if value in UNLOCK_TIERS else None

    def _template_target_skin_id(self, tier, index):
        tier_ids = [
            skin["id"]
            for skin in self.all()
            if str((skin.get("unlock") or {}).get("tier") or "").lower() == tier
        ]
        if index <= len(tier_ids):
            return tier_ids[index - 1]
        candidate = f"{tier}_{index:02d}"
        while candidate in self._skins:
            index += 1
            candidate = f"{tier}_{index:02d}"
        return candidate

    def _skin_from_template(self, folder, tier, index, skin_id):
        base = deepcopy(self.get(skin_id)) if skin_id in self._skins else {
            "id": skin_id,
            "name": f"{TIER_LABELS_BG[tier]} {index}",
            "description": "Отключва се с добри резултати.",
            "unlock": {
                "tier": tier,
                "total_correct": UNLOCK_TIERS[tier],
                "demo_total_correct": DEMO_UNLOCK_TIERS[tier],
            },
            "colors": DEFAULT_COLORS,
        }
        unlock = dict(base.get("unlock") or {})
        unlock.setdefault("tier", tier)
        unlock.setdefault("total_correct", UNLOCK_TIERS[tier])
        unlock.setdefault("demo_total_correct", DEMO_UNLOCK_TIERS[tier])

        rel_asset_dir = os.path.relpath(folder, APP_DIR).replace(os.sep, "/")
        skin = dict(base)
        skin.update(
            {
                "id": skin_id,
                "name": f"{TIER_LABELS_BG[tier]} {index}",
                "description": "Отключва се с добри резултати.",
                "asset_dir": rel_asset_dir,
                "unlock": unlock,
                "wallpaper": self._first_template_file(folder, "wallpaper", ("jpg", "jpeg", "png", "gif")),
                "music": self._first_template_file(folder, "music", ("mp3", "ogg", "wav")),
                "unlock_sound": self._first_template_file(folder, "unlock_sound", ("mp3", "wav", "ogg")),
                "select_sound": self._first_template_file(folder, "select_sound", ("mp3", "wav", "ogg")),
                "correct_sound": self._first_template_file(folder, "correct_sound", ("mp3", "wav", "ogg")),
                "wrong_sound": self._first_template_file(folder, "wrong_sound", ("mp3", "wav", "ogg")),
                "success_sound": self._first_template_file(folder, ("success_sound", "win_sound"), ("mp3", "wav", "ogg")),
                "fail_sound": self._first_template_file(folder, ("fail_sound", "lose_sound"), ("mp3", "wav", "ogg")),
                "win_image": self._first_template_file(folder, ("win", "success"), ("png", "jpg", "jpeg", "gif")),
                "fail_image": self._first_template_file(folder, ("fail", "lose"), ("png", "jpg", "jpeg", "gif")),
            }
        )
        return skin

    def _first_template_file(self, folder, stem, extensions):
        stems = stem if isinstance(stem, (tuple, list)) else (stem,)
        for current_stem in stems:
            for ext in extensions:
                filename = f"{current_stem}.{ext}"
                if os.path.exists(os.path.join(folder, filename)):
                    return filename
        return None

    def _normalize_skin(self, skin):
        skin_id = str(skin.get("id", "")).strip()
        if not skin_id:
            raise ValueError("Skin id is required.")
        normalized = {
            "id": skin_id,
            "name": str(skin.get("name") or skin_id).strip(),
            "description": str(skin.get("description") or "").strip(),
            "unlock": dict(skin.get("unlock") or {}),
            "colors": dict(DEFAULT_COLORS),
            "asset_dir": skin.get("asset_dir"),
            "wallpaper": skin.get("wallpaper"),
            "music": skin.get("music"),
            "unlock_sound": skin.get("unlock_sound"),
            "select_sound": skin.get("select_sound"),
            "correct_sound": skin.get("correct_sound"),
            "wrong_sound": skin.get("wrong_sound"),
            "success_sound": skin.get("success_sound") or skin.get("win_sound"),
            "fail_sound": skin.get("fail_sound") or skin.get("lose_sound"),
            "win_image": skin.get("win_image") or skin.get("success_image") or skin.get("win_icon"),
            "fail_image": skin.get("fail_image") or skin.get("lose_image") or skin.get("fail_icon"),
            "font_family": skin.get("font_family") or "Arial",
        }
        normalized["colors"].update(dict(skin.get("colors") or {}))
        return normalized

    def get(self, skin_id):
        return self._skins.get(skin_id) or self._skins[DEFAULT_SKIN_ID]

    def all(self):
        return list(self._skins.values())

    def ids(self):
        return [skin["id"] for skin in self.all()]

    def unlocked_for_result(self, correct, total, points=None):
        if points is None:
            points = (correct / total) * 100 if total else 0.0
        unlocked = []
        for skin in self.all():
            if self.is_unlocked_by_result(skin, correct, total, points):
                unlocked.append(skin["id"])
        return unlocked

    def unlocked_for_profile(self, profile, demo=False):
        unlocked = []
        for skin in self.all():
            if self.is_unlocked_by_profile(skin, profile, demo=demo):
                unlocked.append(skin["id"])
        return unlocked

    def is_unlocked_by_profile(self, skin, profile, demo=False):
        unlock = skin.get("unlock") or {}
        if not unlock:
            return True

        total_correct = int((profile or {}).get("total_correct") or 0)
        best_correct = int((profile or {}).get("best_correct") or 0)
        best_points = float((profile or {}).get("best_points") or 0.0)
        completed_tests = int((profile or {}).get("completed_tests") or 0)

        threshold = self.total_correct_threshold(skin, demo=demo)
        if threshold is not None and total_correct >= threshold:
            return True

        min_correct = unlock.get("min_correct")
        min_points = unlock.get("min_points")
        min_tests = unlock.get("completed_tests")
        if min_correct is not None and best_correct >= int(min_correct or 0):
            return True
        if min_points is not None and best_points >= float(min_points):
            return True
        if min_tests is not None and completed_tests >= int(min_tests or 0):
            return True
        return False

    def is_unlocked_by_result(self, skin, correct, total, points):
        unlock = skin.get("unlock") or {}
        min_correct = unlock.get("min_correct")
        min_points = unlock.get("min_points")
        if not unlock:
            return True
        correct_ok = min_correct is not None and correct >= int(min_correct)
        points_ok = min_points is not None and points >= float(min_points)
        return correct_ok or points_ok

    def total_correct_threshold(self, skin, demo=False):
        unlock = skin.get("unlock") or {}
        if not unlock:
            return None
        if demo:
            if unlock.get("demo_total_correct") is not None:
                return int(unlock.get("demo_total_correct") or 0)
            tier = str(unlock.get("tier") or "").lower()
            if tier in DEMO_UNLOCK_TIERS:
                return DEMO_UNLOCK_TIERS[tier]
            if unlock.get("total_correct") is not None:
                return min(max(1, int(unlock.get("total_correct") or 1)), DEMO_UNLOCK_TIERS["hard"])
        if unlock.get("total_correct") is not None:
            return int(unlock.get("total_correct") or 0)
        tier = str(unlock.get("tier") or "").lower()
        if tier in UNLOCK_TIERS:
            return UNLOCK_TIERS[tier]
        return None

    def requirement_label(self, skin):
        unlock = skin.get("unlock") or {}
        parts = []
        threshold = self.total_correct_threshold(skin)
        tier = unlock.get("tier")
        min_correct = unlock.get("min_correct")
        min_points = unlock.get("min_points")
        min_tests = unlock.get("completed_tests")
        if threshold is not None:
            tier_text = f" ({TIER_NAMES_BG.get(str(tier).lower(), tier)})" if tier else ""
            parts.append(f"{int(threshold)} верни отговора общо{tier_text}")
        if min_correct:
            parts.append(f"{int(min_correct)} верни отговора в един тест")
        if min_points:
            parts.append(f"{float(min_points):.0f}% най-добър резултат")
        if min_tests:
            parts.append(f"{int(min_tests)} завършени теста")
        return " или ".join(parts) if parts else "отключен"

    def demo_requirement_label(self, skin):
        threshold = self.total_correct_threshold(skin, demo=True)
        if threshold is None:
            return "отключен"
        return f"{threshold} демо верни отговора"

    def colors(self, skin_id):
        return deepcopy(self.get(skin_id).get("colors") or DEFAULT_COLORS)

    def asset_path(self, skin_or_id, field):
        skin = self.get(skin_or_id) if isinstance(skin_or_id, str) else skin_or_id
        value = skin.get(field)
        if not value:
            return None
        value = str(value)
        if os.path.isabs(value):
            return value if os.path.exists(value) else None
        asset_dir = skin.get("asset_dir")
        asset_candidates = []
        if asset_dir:
            asset_dir = str(asset_dir)
            if os.path.isabs(asset_dir):
                asset_candidates.append(os.path.join(asset_dir, value))
            else:
                asset_candidates.extend(
                    [
                        os.path.join(APP_DIR, asset_dir, value),
                        resource_path(os.path.join(asset_dir, value)),
                        os.path.join(self.skins_dir, asset_dir, value),
                        os.path.join(TEMPLATES_DIR, asset_dir, value),
                    ]
                )
        candidates = [
            *asset_candidates,
            os.path.join(APP_DIR, value),
            os.path.join(self.skins_dir, skin["id"], value),
            os.path.join(self.skins_dir, value),
            os.path.join(TEMPLATES_DIR, skin["id"], value),
            os.path.join(TEMPLATES_DIR, value),
            resource_path(value),
            resource_path(os.path.join("skins", skin["id"], value)),
            resource_path(os.path.join("skins", value)),
            resource_path(os.path.join("templates", skin["id"], value)),
            resource_path(os.path.join("templates", value)),
        ]
        return next((path for path in candidates if os.path.exists(path)), None)
