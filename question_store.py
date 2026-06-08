import random
from datetime import datetime
from pathlib import Path

import pandas as pd

from answer_utils import split_answers
from config import BG_LETTERS_BY_COUNT, LETTER_MAP_EN_TO_BG, QUESTIONS_DIR


REQUIRED_COLUMNS = [
    "question",
    "type",
    "option1",
    "option2",
    "option3",
    "option4",
    "answer",
    "image",
    "compare",
]
EXCEL_REQUIRED_COLUMNS = ["subject", "grade", *REQUIRED_COLUMNS]
DEDUP_COLUMNS = ["type", "question", "image", "option1", "option2", "option3", "option4", "answer", "compare"]


def grade_folder_name(grade: str) -> str:
    mapping = {
        "НВО 4 клас": "4",
        "НВО 7 клас": "7",
        "НВО 10 клас": "10",
        "НВО 12 клас": "12",
        "Импорт от Excel": "import",
    }
    return mapping.get(grade, "import")


def subject_folder_name(subject: str) -> str:
    return "bel" if subject == "БЕЛ" else "math"


def ensure_question_folder(subject: str, grade: str) -> Path:
    subj = subject_folder_name(subject or "БЕЛ")
    grd = grade_folder_name(grade or "Импорт от Excel")
    folder = Path(QUESTIONS_DIR) / subj / grd
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _read_csv(path):
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except Exception:
        return pd.read_csv(path, encoding="cp1251")


def _normalize_answer_letters(value: str) -> str:
    value = str(value).strip()
    if not value:
        return ""
    parts = [part.strip() for part in value.split(";") if part.strip()]
    return ";".join(LETTER_MAP_EN_TO_BG.get(part, part) for part in parts)


def store_excel_questions(xlsx_path: str) -> dict:
    df = pd.read_excel(xlsx_path, engine="openpyxl").fillna("")
    for col in EXCEL_REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    ts_now = datetime.now().isoformat(timespec="seconds")
    has_opt_count = "options_count" in df.columns
    has_ans_letters = "answer_letters" in df.columns

    if has_opt_count:
        df["options_count"] = pd.to_numeric(df["options_count"], errors="coerce").fillna(0).astype(int)
    else:
        df["options_count"] = 0

    if has_ans_letters:
        df["answer_letters"] = df["answer_letters"].apply(_normalize_answer_letters)
    else:
        df["answer_letters"] = ""

    stats = {}
    for (subject, grade), sub in df.groupby(["subject", "grade"], dropna=False):
        folder = ensure_question_folder(str(subject), str(grade))
        pool = folder / "pool.csv"
        rows = []

        for _, row in sub.iterrows():
            qtype = str(row["type"]).strip().lower()
            qtext = str(row["question"]).strip()
            opts = [str(row[col]).strip() for col in ("option1", "option2", "option3", "option4")]
            image = str(row["image"]).strip()
            compare = str(row["compare"]).strip().lower() or "exact"
            answer_text = str(row["answer"]).strip()
            options_count = int(row["options_count"]) if has_opt_count else 0
            answer_letters = str(row["answer_letters"]).strip() if has_ans_letters else ""

            if qtype in ("mcq", "mcq_img", "mcq_multi"):
                if all(opt == "" for opt in opts) and options_count in (3, 4):
                    letters = BG_LETTERS_BY_COUNT[options_count]
                    opts = letters + [""] * (4 - len(letters))
                    if not answer_text and answer_letters:
                        answer_text = answer_letters
                elif answer_text and not answer_letters:
                    parts = [part.strip() for part in answer_text.split(";") if part.strip()]
                    if all(part.upper() in ("A", "B", "C", "D") for part in parts):
                        answer_text = ";".join(LETTER_MAP_EN_TO_BG.get(part, part) for part in parts)

            rows.append({
                "question": qtext,
                "type": qtype,
                "option1": opts[0] if len(opts) > 0 else "",
                "option2": opts[1] if len(opts) > 1 else "",
                "option3": opts[2] if len(opts) > 2 else "",
                "option4": opts[3] if len(opts) > 3 else "",
                "answer": answer_text,
                "image": image,
                "compare": compare,
                "added_at": ts_now,
            })

        new_rows = pd.DataFrame(rows)
        if pool.exists():
            old = _read_csv(pool)
            if "added_at" not in old.columns:
                old["added_at"] = ""
            old_len = len(old)
            combined = pd.concat([old, new_rows], ignore_index=True)
            combined = combined.drop_duplicates(subset=DEDUP_COLUMNS, keep="first")
        else:
            old_len = 0
            combined = new_rows.drop_duplicates(subset=DEDUP_COLUMNS, keep="first")

        added = len(combined) - old_len
        combined.to_csv(pool, index=False, encoding="utf-8-sig")
        stats[(str(subject), str(grade))] = (int(added), int(len(combined)))

    return stats


def delete_question_csvs(subject: str, grade: str):
    folder = ensure_question_folder(subject, grade)
    if not folder.exists():
        return 0, str(folder)
    count = 0
    for path in folder.glob("*.csv"):
        try:
            path.unlink()
            count += 1
        except Exception:
            pass
    return count, str(folder)


def load_question_records(subject: str, category: str, sample_size=None):
    folder = ensure_question_folder(subject, category)
    csv_files = list(folder.glob("*.csv"))
    if not csv_files:
        return [], folder, "missing"

    dfs = [_read_csv(path) for path in csv_files]
    df_all = pd.concat(dfs, ignore_index=True).fillna("")
    for col in REQUIRED_COLUMNS:
        if col not in df_all.columns:
            df_all[col] = ""

    seen = set()
    records = []
    for _, row in df_all.iterrows():
        qtype = str(row["type"]).strip().lower() or "free"
        question = str(row["question"]).strip()
        options = [str(row[col]).strip() for col in ("option1", "option2", "option3", "option4") if str(row[col]).strip()]
        image = str(row["image"]).strip()
        compare = str(row["compare"]).strip().lower() or "exact"
        answers = str(row["answer"]).strip()
        answers_set = split_answers(answers) if qtype != "mcq" else {answers}

        key = question.lower() if question else f"image:{image.lower()}"
        if key in seen:
            continue
        seen.add(key)

        records.append({
            "subject": subject,
            "grade": category,
            "type": qtype,
            "question": question,
            "options": options,
            "image": image,
            "compare": compare,
            "answers_set": answers_set,
        })

    if not records:
        return [], folder, "empty"

    if sample_size:
        sample_count = min(int(sample_size), len(records))
        records = random.sample(records, sample_count)
    else:
        random.shuffle(records)

    return records, folder, None
