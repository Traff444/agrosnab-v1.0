"""Tests for keyboard builders."""

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup


class TestPersistentMenu:
    """Tests for persistent_menu() function."""

    def test_returns_reply_keyboard(self):
        from app.keyboards import persistent_menu

        kb = persistent_menu()
        assert isinstance(kb, ReplyKeyboardMarkup)

    def test_has_resize_keyboard(self):
        from app.keyboards import persistent_menu

        kb = persistent_menu()
        assert kb.resize_keyboard is True

    def test_is_persistent(self):
        from app.keyboards import persistent_menu

        kb = persistent_menu()
        assert kb.is_persistent is True

    def test_has_two_rows(self):
        from app.keyboards import persistent_menu

        kb = persistent_menu()
        assert len(kb.keyboard) == 2

    def test_buttons_text(self):
        from app.keyboards import persistent_menu

        kb = persistent_menu()
        texts = [btn.text for row in kb.keyboard for btn in row]
        assert "🗂 Каталог" in texts
        assert "🧺 Корзина" in texts
        assert "🤖 AI Менеджер" in texts
        assert "📋 Меню" in texts


class TestMainMenuKb:
    """Tests for main_menu_kb() function."""

    def test_returns_inline_keyboard(self):
        from app.keyboards import main_menu_kb

        kb = main_menu_kb()
        assert isinstance(kb, InlineKeyboardMarkup)

    def test_has_five_rows(self):
        from app.keyboards import main_menu_kb

        kb = main_menu_kb()
        assert len(kb.inline_keyboard) == 5

    def test_callback_data(self):
        from app.keyboards import main_menu_kb

        kb = main_menu_kb()
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert "catalog:0:all" in callbacks
        assert "cart:show" in callbacks
        assert "search:start" in callbacks
        assert "categories" in callbacks
        assert "mode:ai" in callbacks
        assert "info:terms" in callbacks

    def test_cart_count_displayed(self):
        from app.keyboards import main_menu_kb

        kb = main_menu_kb(cart_count=5)
        texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert any("(5)" in t for t in texts)

    def test_cart_count_zero_no_parentheses(self):
        from app.keyboards import main_menu_kb

        kb = main_menu_kb(cart_count=0)
        texts = [btn.text for row in kb.inline_keyboard for btn in row]
        cart_text = next(t for t in texts if "Корзина" in t)
        assert "(" not in cart_text


class TestCategoriesKb:
    """Tests for categories_kb() function."""

    def test_empty_categories(self):
        from app.keyboards import categories_kb

        kb = categories_kb([])
        # Should have "All" button + "Menu" button
        assert len(kb.inline_keyboard) == 2

    def test_single_category(self):
        from app.keyboards import categories_kb

        kb = categories_kb(["табак"])
        # "All" + category row + "Menu"
        assert len(kb.inline_keyboard) == 3
        assert "табак" in kb.inline_keyboard[1][0].text

    def test_two_categories_same_row(self):
        from app.keyboards import categories_kb

        kb = categories_kb(["табак", "аксессуары"])
        # "All" + one row with 2 categories + "Menu"
        assert len(kb.inline_keyboard) == 3
        assert len(kb.inline_keyboard[1]) == 2

    def test_three_categories_two_rows(self):
        from app.keyboards import categories_kb

        kb = categories_kb(["табак", "аксессуары", "трубки"])
        # "All" + 2 rows of categories + "Menu"
        assert len(kb.inline_keyboard) == 4
        assert len(kb.inline_keyboard[1]) == 2  # First category row
        assert len(kb.inline_keyboard[2]) == 1  # Second category row

    def test_all_button_first(self):
        from app.keyboards import categories_kb

        kb = categories_kb(["test"])
        assert "Все товары" in kb.inline_keyboard[0][0].text
        assert kb.inline_keyboard[0][0].callback_data == "catalog:0:all"

    def test_menu_button_last(self):
        from app.keyboards import categories_kb

        kb = categories_kb(["test"])
        last_row = kb.inline_keyboard[-1]
        assert "Меню" in last_row[0].text
        assert last_row[0].callback_data == "menu"

    def test_category_callback_data(self):
        from app.keyboards import categories_kb

        kb = categories_kb(["премиум"])
        # Find category button
        cat_btn = kb.inline_keyboard[1][0]
        assert cat_btn.callback_data == "catalog:0:премиум"


class TestCatalogPageKb:
    """Tests for catalog_page_kb() function."""

    def test_no_pagination(self):
        from app.keyboards import catalog_page_kb

        kb = catalog_page_kb(page=0, has_prev=False, has_next=False, total_items=5)
        # Page info only (no arrows)
        assert len(kb.inline_keyboard[0]) == 1
        assert "📄" in kb.inline_keyboard[0][0].text

    def test_has_next_only(self):
        from app.keyboards import catalog_page_kb

        kb = catalog_page_kb(page=0, has_prev=False, has_next=True, total_items=10)
        first_row = kb.inline_keyboard[0]
        assert len(first_row) == 2
        assert "➡️" in first_row[-1].text

    def test_has_prev_only(self):
        from app.keyboards import catalog_page_kb

        kb = catalog_page_kb(page=2, has_prev=True, has_next=False, total_items=10)
        first_row = kb.inline_keyboard[0]
        assert len(first_row) == 2
        assert "⬅️" in first_row[0].text

    def test_has_both_prev_and_next(self):
        from app.keyboards import catalog_page_kb

        kb = catalog_page_kb(page=1, has_prev=True, has_next=True, total_items=15)
        first_row = kb.inline_keyboard[0]
        assert len(first_row) == 3
        assert "⬅️" in first_row[0].text
        assert "➡️" in first_row[-1].text

    def test_page_info_display(self):
        from app.keyboards import catalog_page_kb

        kb = catalog_page_kb(page=2, has_prev=False, has_next=False, total_items=25)
        page_btn = kb.inline_keyboard[0][0]
        assert "3" in page_btn.text  # Page is 0-indexed, display is 1-indexed
        assert "25" in page_btn.text

    def test_category_in_callback(self):
        from app.keyboards import catalog_page_kb

        kb = catalog_page_kb(
            page=0, has_prev=False, has_next=True, category="премиум", total_items=5
        )
        next_btn = kb.inline_keyboard[0][-1]
        assert "премиум" in next_btn.callback_data

    def test_has_categories_and_cart_buttons(self):
        from app.keyboards import catalog_page_kb

        kb = catalog_page_kb(page=0, has_prev=False, has_next=False, total_items=5)
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert "categories" in callbacks
        assert "cart:show" in callbacks
        assert "menu" in callbacks


class TestProductKb:
    """Tests for product_kb() function."""

    def test_returns_inline_keyboard(self):
        from app.keyboards import product_kb

        kb = product_kb("SKU-001")
        assert isinstance(kb, InlineKeyboardMarkup)

    def test_add_buttons(self):
        from app.keyboards import product_kb

        kb = product_kb("SKU-001")
        first_row = kb.inline_keyboard[0]
        assert len(first_row) == 2
        assert "add:SKU-001:1" in first_row[0].callback_data
        assert "add:SKU-001:5" in first_row[1].callback_data

    def test_cart_and_back_buttons(self):
        from app.keyboards import product_kb

        kb = product_kb("TEST")
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert "cart:show" in callbacks
        assert "catalog:0:all" in callbacks

    def test_cart_count_displayed(self):
        from app.keyboards import product_kb

        kb = product_kb("SKU-001", cart_count=3)
        texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert any("(3)" in t for t in texts)


class TestCartKb:
    """Tests for cart_kb() function."""

    def test_returns_inline_keyboard(self):
        from app.keyboards import cart_kb

        kb = cart_kb()
        assert isinstance(kb, InlineKeyboardMarkup)

    def test_checkout_and_clear_buttons(self):
        from app.keyboards import cart_kb

        kb = cart_kb()
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert "checkout:start" in callbacks
        assert "cart:clear" in callbacks

    def test_navigation_buttons(self):
        from app.keyboards import cart_kb

        kb = cart_kb()
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert "catalog:0:all" in callbacks
        assert "menu" in callbacks


class TestCartItemKb:
    """Tests for cart_item_kb() function."""

    def test_returns_list_of_buttons(self):
        from app.keyboards import cart_item_kb

        buttons = cart_item_kb("SKU-001", 3)
        assert isinstance(buttons, list)
        assert len(buttons) == 4

    def test_decrease_button(self):
        from app.keyboards import cart_item_kb

        buttons = cart_item_kb("SKU-001", 5)
        assert buttons[0].text == "➖"
        assert buttons[0].callback_data == "cart:dec:SKU-001"

    def test_quantity_display(self):
        from app.keyboards import cart_item_kb

        buttons = cart_item_kb("SKU-001", 7)
        assert buttons[1].text == "7 шт."
        assert buttons[1].callback_data == "noop"

    def test_increase_button(self):
        from app.keyboards import cart_item_kb

        buttons = cart_item_kb("SKU-001", 5)
        assert buttons[2].text == "➕"
        assert buttons[2].callback_data == "cart:inc:SKU-001"

    def test_remove_button(self):
        from app.keyboards import cart_item_kb

        buttons = cart_item_kb("SKU-001", 5)
        assert buttons[3].text == "🗑"
        assert buttons[3].callback_data == "cart:remove:SKU-001"


class TestCartWithItemsKb:
    """Tests for cart_with_items_kb() function."""

    def test_empty_items(self):
        from app.keyboards import cart_with_items_kb

        kb = cart_with_items_kb([])
        # Only action rows (checkout/clear + catalog/menu)
        assert len(kb.inline_keyboard) == 2

    def test_single_item(self):
        from app.keyboards import cart_with_items_kb

        items = [("SKU-001", 2, "Товар первый")]
        kb = cart_with_items_kb(items)
        # Item name row + controls row + 2 action rows
        assert len(kb.inline_keyboard) == 4

    def test_multiple_items(self):
        from app.keyboards import cart_with_items_kb

        items = [
            ("SKU-001", 2, "Товар первый"),
            ("SKU-002", 3, "Товар второй"),
        ]
        kb = cart_with_items_kb(items)
        # 2 items * 2 rows each + 2 action rows = 6
        assert len(kb.inline_keyboard) == 6

    def test_long_name_truncated(self):
        from app.keyboards import cart_with_items_kb

        items = [("SKU-001", 1, "Очень длинное название товара которое не помещается")]
        kb = cart_with_items_kb(items)
        name_btn = kb.inline_keyboard[0][0]
        assert len(name_btn.text) <= 25  # 📦 + space + 20 chars + …
        assert "…" in name_btn.text

    def test_short_name_not_truncated(self):
        from app.keyboards import cart_with_items_kb

        items = [("SKU-001", 1, "Короткое")]
        kb = cart_with_items_kb(items)
        name_btn = kb.inline_keyboard[0][0]
        assert "Короткое" in name_btn.text
        assert "…" not in name_btn.text

    def test_item_callback_data(self):
        from app.keyboards import cart_with_items_kb

        items = [("SKU-001", 1, "Товар")]
        kb = cart_with_items_kb(items)
        name_btn = kb.inline_keyboard[0][0]
        assert name_btn.callback_data == "product:SKU-001"

    def test_has_action_buttons(self):
        from app.keyboards import cart_with_items_kb

        items = [("SKU-001", 1, "Товар")]
        kb = cart_with_items_kb(items)
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert "checkout:start" in callbacks
        assert "cart:clear" in callbacks
        assert "catalog:0:all" in callbacks
        assert "menu" in callbacks


class TestBackToMenuKb:
    """Tests for back_to_menu_kb() function."""

    def test_returns_inline_keyboard(self):
        from app.keyboards import back_to_menu_kb

        kb = back_to_menu_kb()
        assert isinstance(kb, InlineKeyboardMarkup)

    def test_single_button(self):
        from app.keyboards import back_to_menu_kb

        kb = back_to_menu_kb()
        assert len(kb.inline_keyboard) == 1
        assert len(kb.inline_keyboard[0]) == 1

    def test_menu_callback(self):
        from app.keyboards import back_to_menu_kb

        kb = back_to_menu_kb()
        assert kb.inline_keyboard[0][0].callback_data == "menu"


class TestCitySelectKb:
    """Tests for city_select_kb() function."""

    def test_empty_cities(self):
        from app.keyboards import city_select_kb

        kb = city_select_kb([])
        # Only action row (retry + manual)
        assert len(kb.inline_keyboard) == 1

    def test_single_city(self):
        from app.keyboards import city_select_kb

        cities = [(123, "Москва")]
        kb = city_select_kb(cities)
        # City row + action row
        assert len(kb.inline_keyboard) == 2
        assert "Москва" in kb.inline_keyboard[0][0].text
        assert kb.inline_keyboard[0][0].callback_data == "cdek:city:123"

    def test_max_ten_cities(self):
        from app.keyboards import city_select_kb

        cities = [(i, f"City {i}") for i in range(15)]
        kb = city_select_kb(cities)
        # Max 10 cities + action row
        assert len(kb.inline_keyboard) == 11

    def test_long_city_name_truncated(self):
        from app.keyboards import city_select_kb

        cities = [(1, "Очень длинное название города которое не помещается в кнопку")]
        kb = city_select_kb(cities)
        btn = kb.inline_keyboard[0][0]
        assert len(btn.text) <= 40  # 📍 + space + truncated name
        assert "..." in btn.text

    def test_action_buttons(self):
        from app.keyboards import city_select_kb

        kb = city_select_kb([])
        action_row = kb.inline_keyboard[-1]
        callbacks = [btn.callback_data for btn in action_row]
        assert "cdek:city:retry" in callbacks
        assert "cdek:manual" in callbacks


class TestPvzSelectKb:
    """Tests for pvz_select_kb() function."""

    def test_empty_pvz_list(self):
        from app.keyboards import pvz_select_kb

        kb = pvz_select_kb([], city_code=123)
        # Only action row
        assert len(kb.inline_keyboard) == 1

    def test_single_pvz(self):
        from app.keyboards import pvz_select_kb

        pvz_list = [("PVZ-1", "ул. Ленина, 10")]
        kb = pvz_select_kb(pvz_list, city_code=123)
        # PVZ row + action row (no pagination for 1 item)
        assert len(kb.inline_keyboard) == 2
        assert "Ленина" in kb.inline_keyboard[0][0].text

    def test_pvz_callback_data(self):
        from app.keyboards import pvz_select_kb

        pvz_list = [("PVZ-ABC", "Address")]
        kb = pvz_select_kb(pvz_list, city_code=123)
        assert kb.inline_keyboard[0][0].callback_data == "cdek:pvz:PVZ-ABC"

    def test_pagination_not_shown_for_few_items(self):
        from app.keyboards import pvz_select_kb

        pvz_list = [(f"PVZ-{i}", f"Address {i}") for i in range(5)]
        kb = pvz_select_kb(pvz_list, city_code=123, page=0)
        # 5 PVZ rows + action row (no pagination)
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert not any("pvz_page" in c for c in callbacks)

    def test_pagination_shown_for_many_items(self):
        from app.keyboards import pvz_select_kb

        pvz_list = [(f"PVZ-{i}", f"Address {i}") for i in range(20)]
        kb = pvz_select_kb(pvz_list, city_code=123, page=0)
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        # Should have next page button
        assert any("pvz_page:123:1" in c for c in callbacks)

    def test_first_page_no_prev_button(self):
        from app.keyboards import pvz_select_kb

        pvz_list = [(f"PVZ-{i}", f"Address {i}") for i in range(20)]
        kb = pvz_select_kb(pvz_list, city_code=123, page=0)
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        # No prev button on first page
        assert not any("pvz_page:123:-1" in c for c in callbacks)

    def test_middle_page_has_both_buttons(self):
        from app.keyboards import pvz_select_kb

        pvz_list = [(f"PVZ-{i}", f"Address {i}") for i in range(25)]
        kb = pvz_select_kb(pvz_list, city_code=123, page=1)
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        # Both prev and next
        assert any("pvz_page:123:0" in c for c in callbacks)  # prev
        assert any("pvz_page:123:2" in c for c in callbacks)  # next

    def test_last_page_no_next_button(self):
        from app.keyboards import pvz_select_kb

        pvz_list = [(f"PVZ-{i}", f"Address {i}") for i in range(16)]  # 2 pages
        kb = pvz_select_kb(pvz_list, city_code=123, page=1)
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        # No next button on last page
        assert not any("pvz_page:123:2" in c for c in callbacks)

    def test_page_indicator(self):
        from app.keyboards import pvz_select_kb

        pvz_list = [(f"PVZ-{i}", f"Address {i}") for i in range(20)]
        kb = pvz_select_kb(pvz_list, city_code=123, page=1)
        # Find page indicator
        texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert any("2/3" in t for t in texts)

    def test_long_address_truncated(self):
        from app.keyboards import pvz_select_kb

        pvz_list = [("PVZ-1", "Очень длинный адрес который не помещается в кнопку целиком")]
        kb = pvz_select_kb(pvz_list, city_code=123)
        btn = kb.inline_keyboard[0][0]
        assert "..." in btn.text

    def test_action_buttons(self):
        from app.keyboards import pvz_select_kb

        kb = pvz_select_kb([], city_code=123)
        action_row = kb.inline_keyboard[-1]
        callbacks = [btn.callback_data for btn in action_row]
        assert "cdek:city:retry" in callbacks
        assert "cdek:manual" in callbacks


class TestDeliveryConfirmKb:
    """Tests for delivery_confirm_kb() function."""

    def test_returns_inline_keyboard(self):
        from app.keyboards import delivery_confirm_kb

        kb = delivery_confirm_kb()
        assert isinstance(kb, InlineKeyboardMarkup)

    def test_has_two_buttons(self):
        from app.keyboards import delivery_confirm_kb

        kb = delivery_confirm_kb()
        assert len(kb.inline_keyboard) == 1
        assert len(kb.inline_keyboard[0]) == 2

    def test_confirm_button(self):
        from app.keyboards import delivery_confirm_kb

        kb = delivery_confirm_kb()
        confirm_btn = kb.inline_keyboard[0][0]
        assert "Подтвердить" in confirm_btn.text
        assert confirm_btn.callback_data == "cdek:confirm"

    def test_change_button(self):
        from app.keyboards import delivery_confirm_kb

        kb = delivery_confirm_kb()
        change_btn = kb.inline_keyboard[0][1]
        assert "Изменить" in change_btn.text
        assert change_btn.callback_data == "cdek:city:retry"


class TestPvzPerPageConstant:
    """Tests for PVZ_PER_PAGE constant."""

    def test_constant_value(self):
        from app.keyboards import PVZ_PER_PAGE

        assert PVZ_PER_PAGE == 8

    def test_pagination_uses_constant(self):
        from app.keyboards import PVZ_PER_PAGE, pvz_select_kb

        # Create exactly PVZ_PER_PAGE + 1 items to trigger pagination
        pvz_list = [(f"PVZ-{i}", f"Address {i}") for i in range(PVZ_PER_PAGE + 1)]
        kb = pvz_select_kb(pvz_list, city_code=123, page=0)

        # First page should show PVZ_PER_PAGE items + pagination row + action row
        pvz_buttons = [
            row for row in kb.inline_keyboard if row[0].callback_data.startswith("cdek:pvz:")
        ]
        assert len(pvz_buttons) == PVZ_PER_PAGE


class TestCatalogGridKb:
    """Tests for catalog_grid_kb() function."""

    def test_returns_inline_keyboard(self):
        from app.keyboards import catalog_grid_kb

        products = [{"sku": "SKU-1", "name": "Test", "price_rub": 100}]
        kb = catalog_grid_kb(products, page=0)
        assert isinstance(kb, InlineKeyboardMarkup)

    def test_empty_products(self):
        from app.keyboards import catalog_grid_kb

        kb = catalog_grid_kb([], page=0, category="all")
        # Should have navigation + categories + cart rows
        assert len(kb.inline_keyboard) >= 3

    def test_six_products_per_page(self):
        from app.keyboards import CATALOG_PAGE_SIZE, catalog_grid_kb

        products = [
            {"sku": f"SKU-{i}", "name": f"Product {i}", "price_rub": 100} for i in range(10)
        ]
        kb = catalog_grid_kb(products, page=0, category="all")
        # Each product gets its own row (1 column layout)
        product_rows = [
            row for row in kb.inline_keyboard if any("product:" in btn.callback_data for btn in row)
        ]
        assert len(product_rows) == CATALOG_PAGE_SIZE  # 8 rows for 8 items (1 per row)

    def test_cart_count_displayed(self):
        from app.keyboards import catalog_grid_kb

        products = [{"sku": "SKU-1", "name": "Test", "price_rub": 100}]
        kb = catalog_grid_kb(products, page=0, cart_count=5)
        texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert any("(5)" in t for t in texts)

    def test_product_name_truncated(self):
        from app.keyboards import catalog_grid_kb

        # Name must exceed max_total (48) - price suffix (~10 chars) = 38+ chars to trigger truncation
        products = [
            {
                "sku": "SKU-1",
                "name": "Very Long Product Name That Exceeds Maximum Length Limit",
                "price_rub": 100,
            }
        ]
        kb = catalog_grid_kb(products, page=0)
        product_btn = kb.inline_keyboard[0][0]
        # Name should be truncated with ellipsis
        assert "…" in product_btn.text

    def test_pagination_navigation(self):
        from app.keyboards import catalog_grid_kb

        products = [
            {"sku": f"SKU-{i}", "name": f"Product {i}", "price_rub": 100} for i in range(15)
        ]
        kb = catalog_grid_kb(products, page=0, category="test")
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        # Should have next page button
        assert any("catalog:1:test" in c for c in callbacks)

    def test_category_in_navigation(self):
        from app.keyboards import catalog_grid_kb

        products = [
            {"sku": f"SKU-{i}", "name": f"Product {i}", "price_rub": 100} for i in range(15)
        ]
        kb = catalog_grid_kb(products, page=0, category="премиум")
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert any("премиум" in c for c in callbacks)

    def test_page_indicator_shows_correct_total(self):
        from app.keyboards import catalog_grid_kb

        # With CATALOG_PAGE_SIZE=8: 17 products = 3 pages (8+8+1)
        products = [
            {"sku": f"SKU-{i}", "name": f"Product {i}", "price_rub": 100} for i in range(17)
        ]  # 3 pages
        kb = catalog_grid_kb(products, page=1, category="all")
        texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert any("2/3" in t for t in texts)

    def test_empty_products_shows_1_1_pages(self):
        from app.keyboards import catalog_grid_kb

        kb = catalog_grid_kb([], page=0)
        texts = [btn.text for row in kb.inline_keyboard for btn in row]
        # Should show "1/1" not "1/0"
        assert any("1/1" in t for t in texts)


class TestOrderConfirmKb:
    """Tests for order_confirm_kb() function."""

    def test_returns_inline_keyboard(self):
        from app.keyboards import order_confirm_kb

        kb = order_confirm_kb()
        assert isinstance(kb, InlineKeyboardMarkup)

    def test_has_confirm_button(self):
        from app.keyboards import order_confirm_kb

        kb = order_confirm_kb()
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert "checkout:final" in callbacks

    def test_has_edit_buttons(self):
        from app.keyboards import order_confirm_kb

        kb = order_confirm_kb()
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert "checkout:edit:phone" in callbacks
        assert "checkout:edit:delivery" in callbacks

    def test_has_cancel_button(self):
        from app.keyboards import order_confirm_kb

        kb = order_confirm_kb()
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert "cart:show" in callbacks

    def test_confirm_button_text(self):
        from app.keyboards import order_confirm_kb

        kb = order_confirm_kb()
        confirm_btn = kb.inline_keyboard[0][0]
        assert "Подтвердить" in confirm_btn.text


class TestCatalogPageSizeConstant:
    """Tests for CATALOG_PAGE_SIZE constant."""

    def test_constant_value(self):
        from app.keyboards import CATALOG_PAGE_SIZE

        assert CATALOG_PAGE_SIZE == 8
