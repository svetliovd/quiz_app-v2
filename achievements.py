import datetime as _dt
import hashlib
import hmac
import json
import uuid
from copy import deepcopy


PROFILE_EXTENSION = ".quizprofile"
PROFILE_VERSION = 1
_SIGNING_KEY = b"QuizApp2 achievement profile v1"


def _now():
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _unsigned(profile):
    data = deepcopy(profile or {})
    data.pop("signature", None)
    return data


def _canonical_bytes(profile):
    return json.dumps(
        _unsigned(profile),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _signature(profile):
    return hmac.new(_SIGNING_KEY, _canonical_bytes(profile), hashlib.sha256).hexdigest()


def verify_profile(profile):
    expected = profile.get("signature") if isinstance(profile, dict) else None
    if not expected:
        return False
    return hmac.compare_digest(str(expected), _signature(profile))


def ensure_profile(profile=None):
    data = _unsigned(profile)
    created = data.get("created_at") or _now()
    data.setdefault("version", PROFILE_VERSION)
    data.setdefault("student_key", str(uuid.uuid4()))
    data.setdefault("display_name", "Student")
    data.setdefault("created_at", created)
    data.setdefault("updated_at", created)
    data.setdefault("completed_tests", 0)
    data.setdefault("total_correct", 0)
    data.setdefault("total_questions", 0)
    data.setdefault("best_correct", 0)
    data.setdefault("best_points", 0.0)
    data.setdefault("best_grade", 0.0)
    data.setdefault("unlocked_skins", ["classic"])
    data.setdefault("selected_skin", "classic")
    data.setdefault("history", [])
    if "classic" not in data["unlocked_skins"]:
        data["unlocked_skins"].append("classic")
    return data


def create_profile(display_name="Student"):
    profile = ensure_profile({"display_name": display_name})
    profile["updated_at"] = _now()
    return profile


def signed_profile(profile):
    data = ensure_profile(profile)
    data["updated_at"] = _now()
    data["signature"] = _signature(data)
    return data


def load_profile(path):
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not verify_profile(data):
        raise ValueError("Profile file is damaged or has been edited.")
    return ensure_profile(data)


def save_profile(profile, path):
    data = signed_profile(profile)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    return path


def update_profile_after_result(profile, *, subject, category, correct, total, points, grade, skin_manager, demo_unlocks=False):
    data = ensure_profile(profile)
    old_unlocked = set(data.get("unlocked_skins") or ["classic"])

    data["completed_tests"] = int(data.get("completed_tests") or 0) + 1
    data["total_correct"] = int(data.get("total_correct") or 0) + int(correct)
    data["total_questions"] = int(data.get("total_questions") or 0) + int(total)

    if int(correct) > int(data.get("best_correct") or 0):
        data["best_correct"] = int(correct)
    if float(points) > float(data.get("best_points") or 0.0):
        data["best_points"] = float(points)
    if float(grade) > float(data.get("best_grade") or 0.0):
        data["best_grade"] = float(grade)

    earned_now = set(skin_manager.unlocked_for_profile(data, demo=demo_unlocks))
    all_unlocked = old_unlocked | earned_now | {"classic"}
    ordered = [skin["id"] for skin in skin_manager.all() if skin["id"] in all_unlocked]
    data["unlocked_skins"] = ordered

    new_unlocked = [skin["id"] for skin in skin_manager.all() if skin["id"] in (all_unlocked - old_unlocked)]
    if new_unlocked:
        data["selected_skin"] = new_unlocked[-1]
    elif data.get("selected_skin") not in all_unlocked:
        data["selected_skin"] = "classic"

    history = list(data.get("history") or [])
    history.append(
        {
            "date": _now(),
            "subject": subject,
            "category": category,
            "correct": int(correct),
            "total": int(total),
            "points": float(points),
            "grade": float(grade),
            "new_skins": new_unlocked,
            "demo_unlocks": bool(demo_unlocks),
        }
    )
    data["history"] = history[-50:]
    data["updated_at"] = _now()
    return data, new_unlocked
