def normalize_answer(value: str) -> str:
    value = (value or "").strip().lower()
    return " ".join(value.split())


def split_answers(answer_text: str):
    if not answer_text:
        return set()
    return {part.strip() for part in answer_text.split(";") if part.strip()}
