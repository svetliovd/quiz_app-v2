import pandas as pd

from config import GRADING_FILE


def load_grading_scale(path: str = GRADING_FILE):
    if not path:
        return pd.DataFrame(columns=["points", "grade"])
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame(columns=["points", "grade"])


def import_grading_scale_csv(source_path: str, target_path: str = GRADING_FILE):
    new_df = pd.read_csv(source_path)
    if "points" not in new_df.columns or "grade" not in new_df.columns:
        raise ValueError("CSV файлът трябва да има колони 'points' и 'grade'.")
    new_df.to_csv(target_path, index=False)
    return new_df


def calculate_grade(points: float, grading_df) -> float:
    if points < 30:
        return 2.00
    if grading_df.empty:
        return 0.0
    idx = (grading_df["points"] - points).abs().idxmin()
    return float(grading_df.loc[idx, "grade"])
