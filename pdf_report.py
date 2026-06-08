import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_pdf_report(
    reports_dir: str,
    subject: str,
    category: str,
    questions_count: int,
    score: int,
    points: float,
    grade: float,
    user_answers,
    pdf_font_name: str,
) -> str:
    os.makedirs(reports_dir, exist_ok=True)
    out_path = os.path.join(reports_dir, f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
    doc = SimpleDocTemplate(out_path, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(name="Title", parent=styles["Title"], fontName=pdf_font_name, fontSize=18)
    style_text = ParagraphStyle(name="Body", parent=styles["BodyText"], fontName=pdf_font_name, fontSize=12, leading=15)
    style_cell = ParagraphStyle(name="Cell", parent=styles["BodyText"], fontName=pdf_font_name, fontSize=10, leading=12)

    elems = []
    elems.append(Paragraph("Отчет за тест", style_title))
    elems.append(Spacer(1, 12))

    info_lines = [
        f"Предмет: {subject or ''}",
        f"Категория: {category or ''}",
        f"Дата/час: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
        f"Въпроси общо: {questions_count}",
        f"Верни отговори: {score}",
        f"Точки: {points:.2f}",
        f"Оценка: {grade:.2f}",
    ]
    for line in info_lines:
        elems.append(Paragraph(line, style_text))

    elems.append(Spacer(1, 18))
    elems.append(Paragraph("Отговори по въпроси:", style_text))
    elems.append(Spacer(1, 8))

    data = [[
        Paragraph("№", style_cell),
        Paragraph("Въпрос", style_cell),
        Paragraph("Отговор", style_cell),
        Paragraph("Верен", style_cell),
        Paragraph("Статус", style_cell),
    ]]
    for i, (q_text, user_ans, correct_ans, is_ok) in enumerate(user_answers, start=1):
        data.append([
            Paragraph(str(i), style_cell),
            Paragraph(str(q_text), style_cell),
            Paragraph(str(user_ans), style_cell),
            Paragraph(str(correct_ans), style_cell),
            Paragraph("Вярно" if is_ok else "Грешно", style_cell),
        ])

    base_widths = [28, 280, 140, 50, 60]
    scale = doc.width / sum(base_widths)
    col_widths = [width * scale for width in base_widths]
    table = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elems.append(table)
    doc.build(elems)
    return out_path
