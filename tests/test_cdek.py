"""Tests for CDEK helpers (keyboards + formatting)."""

from app.cdek import CdekPvz
from app.keyboards import city_select_kb, delivery_confirm_kb, pvz_select_kb


def test_city_select_kb_includes_actions_row():
    kb = city_select_kb([(1, "Москва"), (2, "Санкт‑Петербург")])
    rows = kb.inline_keyboard

    # last row has retry + manual actions
    assert len(rows) >= 2
    last = rows[-1]
    assert len(last) == 2
    assert last[0].callback_data == "cdek:city:retry"
    assert last[1].callback_data == "cdek:manual"


def test_pvz_select_kb_pagination_buttons():
    pvz_items = [(f"PVZ{i}", f"Адрес {i}") for i in range(1, 10)]  # 9 items => 2 pages (8 + 1)
    kb = pvz_select_kb(pvz_items, city_code=44, page=0)
    rows = kb.inline_keyboard

    # There should be PVZ rows + nav row + actions row
    assert len(rows) >= 10

    # nav row should contain page indicator and next button on page 0
    nav_row = rows[8]
    assert any(b.callback_data == "noop" and "1/2" in (b.text or "") for b in nav_row)
    assert any(b.callback_data == "cdek:pvz_page:44:1" for b in nav_row)


def test_delivery_confirm_kb_buttons():
    kb = delivery_confirm_kb()
    rows = kb.inline_keyboard
    assert len(rows) == 1
    assert rows[0][0].callback_data == "cdek:confirm"
    assert rows[0][1].callback_data == "cdek:city:retry"


def test_cdek_pvz_full_display_format():
    pvz = CdekPvz(
        code="PVZ123",
        name="Test PVZ",
        address="Москва, Тверская 1",
        city="Москва",
        work_time="10:00-20:00",
        nearest_metro="Тверская",
    )
    text = pvz.full_display()
    assert "📍" in text
    assert "Тверская 1" in text
    assert "🕐" in text
    assert "🚇" in text

