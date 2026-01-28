from __future__ import annotations

from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

DEJAVU_TTF = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def ensure_font() -> str:
    # Регистрируем шрифт один раз
    try:
        pdfmetrics.getFont("DejaVu")
    except KeyError:
        pdfmetrics.registerFont(TTFont("DejaVu", DEJAVU_TTF))
    return "DejaVu"


def rub(n: int) -> str:
    return f"{n:,}".replace(",", " ") + " ₽"


def generate_invoice_pdf(
    out_path: str,
    *,
    invoice_no: str,
    invoice_date: str,
    seller: dict[str, Any],
    buyer_phone: str,
    delivery: str,
    items: list[tuple[str, str, int, int]],  # sku, name, qty, price
) -> None:
    font = ensure_font()
    c = Canvas(out_path, pagesize=A4)
    w, h = A4

    y = h - 50
    c.setFont(font, 16)
    c.drawString(50, y, f"СЧЕТ № {invoice_no} от {invoice_date}")
    y -= 28

    c.setFont(font, 10)
    c.drawString(50, y, f"Продавец: {seller.get('Орг. продавец (юр. лицо)', '')}")
    y -= 14
    c.drawString(50, y, f"ИНН/ОГРН: {seller.get('ИНН/ОГРН', '')}")
    y -= 14
    c.drawString(50, y, f"Адрес: {seller.get('Адрес продавца', '')}")
    y -= 14
    c.drawString(
        50,
        y,
        f"Контакты: {seller.get('Телефон продавца', '')} • {seller.get('Email продавца', '')}",
    )
    y -= 22

    c.setFont(font, 10)
    c.drawString(50, y, f"Покупатель (телефон): {buyer_phone}")
    y -= 14
    c.drawString(50, y, f"Доставка: {delivery}")
    y -= 22

    # Table header
    c.setFont(font, 10)
    c.drawString(50, y, "№")
    c.drawString(75, y, "SKU")
    c.drawString(150, y, "Наименование")
    c.drawString(400, y, "Кол-во")
    c.drawString(460, y, "Цена")
    c.drawString(520, y, "Сумма")
    y -= 10
    c.line(50, y, 560, y)
    y -= 16

    total = 0
    for idx, (sku, name, qty, price) in enumerate(items, start=1):
        line_sum = qty * price
        total += line_sum
        c.drawString(50, y, str(idx))
        c.drawString(75, y, sku)
        # обрезаем длинное имя
        c.drawString(150, y, (name[:42] + "…") if len(name) > 43 else name)
        c.drawRightString(430, y, str(qty))
        c.drawRightString(505, y, rub(price))
        c.drawRightString(560, y, rub(line_sum))
        y -= 16
        if y < 120:
            c.showPage()
            y = h - 50
            c.setFont(font, 10)

    y -= 6
    c.line(350, y, 560, y)
    y -= 18
    c.setFont(font, 12)
    c.drawRightString(505, y, "ИТОГО:")
    c.drawRightString(560, y, rub(total))

    y -= 26
    c.setFont(font, 9)
    c.drawString(
        50, y, "Оплата означает согласие с условиями поставки/опта (см. «Настройки» и «Поставщик»)."
    )

    c.showPage()
    c.save()
