"""Tests for critical command handlers (/start, /cancel, /help).

These handlers always work regardless of FSM state and are registered
with highest priority in the router chain.

This test file uses subprocess isolation to avoid polluting sys.modules
for other tests in the same session.
"""

import importlib
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import isolation: load critical.py without triggering the full import chain.
#
# The challenge: app.handlers.critical imports intake_service which
# transitively imports cloudinary_client, google-auth, PIL, etc.
# We stub only what's needed, and clean up after ourselves.
# ---------------------------------------------------------------------------

# Modules we'll stub temporarily for import, then clean up
_THIRD_PARTY_STUBS = [
    "PIL", "PIL.Image", "PIL.ImageFilter", "PIL.ImageStat", "PIL.ImageEnhance",
    "cloudinary", "cloudinary.uploader", "cloudinary.utils",
    "google", "google.oauth2", "google.oauth2.service_account",
    "googleapiclient", "googleapiclient.discovery", "googleapiclient.errors",
    "sentry_sdk",
]

# Internal app modules with module-level side effects (to be stubbed and cleaned)
_INTERNAL_STUBS = [
    "app.cloudinary_client", "app.drive", "app.storage",
    "app.storage.intake_sessions", "app.photo_quality", "app.photo_enhance",
    "app.intake_parser", "app.crm_db", "app.monitoring",
    "app.services", "app.services.intake_service", "app.services.product_service",
]

# Ensure owner_bot is on path
_owner_bot_dir = str(Path(__file__).resolve().parent.parent)
if _owner_bot_dir not in sys.path:
    sys.path.insert(0, _owner_bot_dir)

# Ensure env is set
import os
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token")
os.environ.setdefault("OWNER_TELEGRAM_IDS", "123456789")
os.environ.setdefault("GOOGLE_SHEETS_ID", "test_sheet_id")
os.environ.setdefault("GOOGLE_SERVICE_ACCOUNT_JSON_PATH", "/tmp/test.json")
os.environ.setdefault("DRIVE_FOLDER_ID", "test_folder_id")

# Track what we temporarily add so we can clean up only those
_added_modules: dict[str, bool] = {}  # mod_name -> was_absent

# Step 1: Install third-party stubs
for _mod in _THIRD_PARTY_STUBS:
    if _mod not in sys.modules:
        _added_modules[_mod] = True
        sys.modules[_mod] = MagicMock()

# Step 2: Install internal app stubs
for _mod in _INTERNAL_STUBS:
    if _mod not in sys.modules:
        _added_modules[_mod] = True
        sys.modules[_mod] = MagicMock()

# Step 3: Install app.handlers as bare package (skip __init__.py)
_handlers_was_absent = "app.handlers" not in sys.modules
if _handlers_was_absent:
    _handlers_dir = str(Path(__file__).resolve().parent.parent / "app" / "handlers")
    _pkg = ModuleType("app.handlers")
    _pkg.__path__ = [_handlers_dir]
    _pkg.__package__ = "app.handlers"
    sys.modules["app.handlers"] = _pkg

# Step 4: Import the module under test
_critical = importlib.import_module("app.handlers.critical")
cmd_start = _critical.cmd_start
cmd_cancel = _critical.cmd_cancel
cmd_help = _critical.cmd_help

# Step 5: Clean up ONLY the third-party and internal stubs we added.
# Keep app.handlers and app.handlers.critical so @patch can find them.
for _mod, _was_absent in _added_modules.items():
    if _was_absent and _mod in sys.modules:
        del sys.modules[_mod]
_added_modules.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state() -> MagicMock:
    """Create a mock FSMContext with async clear()."""
    state = MagicMock()
    state.clear = AsyncMock()
    return state


def _make_message(
    user_id: int = 123456789,
    first_name: str = "Иван",
    *,
    has_user: bool = True,
) -> MagicMock:
    """Create a mock Message with optional from_user."""
    message = MagicMock()
    message.answer = AsyncMock()

    if has_user:
        user = MagicMock()
        user.id = user_id
        user.first_name = first_name
        message.from_user = user
    else:
        message.from_user = None

    return message


# ---------------------------------------------------------------------------
# /start handler
# ---------------------------------------------------------------------------


class TestCmdStart:
    """Tests for the /start command handler."""

    @pytest.mark.asyncio
    @patch("app.handlers.critical.cleanup_tmp_files", return_value=0)
    @patch("app.handlers.critical.intake_service")
    @patch("app.handlers.critical.main_menu_keyboard")
    async def test_clears_fsm_state(
        self,
        _mock_kb,
        mock_intake,
        _mock_cleanup,
    ):
        """cmd_start must always clear FSM state first."""
        mock_intake.clear_session = AsyncMock()
        state = _make_state()
        message = _make_message()

        await cmd_start(message, state)

        state.clear.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.handlers.critical.cleanup_tmp_files", return_value=0)
    @patch("app.handlers.critical.intake_service")
    @patch("app.handlers.critical.main_menu_keyboard")
    async def test_sends_welcome_text(
        self,
        _mock_kb,
        mock_intake,
        _mock_cleanup,
    ):
        """cmd_start must send a welcome message containing key phrases."""
        mock_intake.clear_session = AsyncMock()
        state = _make_state()
        message = _make_message(first_name="Иван")

        await cmd_start(message, state)

        message.answer.assert_awaited_once()
        text = message.answer.call_args[0][0]
        assert "Добро пожаловать" in text
        assert "Приход товара" in text
        assert "CRM" in text

    @pytest.mark.asyncio
    @patch("app.handlers.critical.cleanup_tmp_files", return_value=0)
    @patch("app.handlers.critical.intake_service")
    @patch("app.handlers.critical.main_menu_keyboard")
    async def test_calls_main_menu_keyboard(
        self,
        mock_kb,
        mock_intake,
        _mock_cleanup,
    ):
        """cmd_start must pass main_menu_keyboard() as reply_markup."""
        mock_intake.clear_session = AsyncMock()
        sentinel_kb = MagicMock(name="keyboard_sentinel")
        mock_kb.return_value = sentinel_kb

        state = _make_state()
        message = _make_message()

        await cmd_start(message, state)

        mock_kb.assert_called_once()
        _, kwargs = message.answer.call_args
        assert kwargs["reply_markup"] is sentinel_kb

    @pytest.mark.asyncio
    @patch("app.handlers.critical.cleanup_tmp_files", return_value=0)
    @patch("app.handlers.critical.intake_service")
    @patch("app.handlers.critical.main_menu_keyboard")
    async def test_greets_user_by_first_name(
        self,
        _mock_kb,
        mock_intake,
        _mock_cleanup,
    ):
        """cmd_start must include the user's first_name in the greeting."""
        mock_intake.clear_session = AsyncMock()
        state = _make_state()
        message = _make_message(first_name="Алексей")

        await cmd_start(message, state)

        text = message.answer.call_args[0][0]
        assert "Алексей" in text

    @pytest.mark.asyncio
    @patch("app.handlers.critical.cleanup_tmp_files", return_value=0)
    @patch("app.handlers.critical.intake_service")
    @patch("app.handlers.critical.main_menu_keyboard")
    async def test_handles_missing_from_user(
        self,
        _mock_kb,
        mock_intake,
        _mock_cleanup,
    ):
        """When message.from_user is None, name defaults to 'Владелец'."""
        mock_intake.clear_session = AsyncMock()
        state = _make_state()
        message = _make_message(has_user=False)

        await cmd_start(message, state)

        text = message.answer.call_args[0][0]
        assert "Владелец" in text

    @pytest.mark.asyncio
    @patch("app.handlers.critical.cleanup_tmp_files", return_value=0)
    @patch("app.handlers.critical.intake_service")
    @patch("app.handlers.critical.main_menu_keyboard")
    async def test_does_not_clear_session_when_no_user(
        self,
        _mock_kb,
        mock_intake,
        _mock_cleanup,
    ):
        """When from_user is None, intake_service.clear_session is NOT called."""
        mock_intake.clear_session = AsyncMock()
        state = _make_state()
        message = _make_message(has_user=False)

        await cmd_start(message, state)

        mock_intake.clear_session.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("app.handlers.critical.cleanup_tmp_files", return_value=0)
    @patch("app.handlers.critical.intake_service")
    @patch("app.handlers.critical.main_menu_keyboard")
    async def test_calls_intake_service_clear_session(
        self,
        _mock_kb,
        mock_intake,
        _mock_cleanup,
    ):
        """cmd_start must clear the intake session for the current user."""
        mock_intake.clear_session = AsyncMock()
        state = _make_state()
        message = _make_message(user_id=42)

        await cmd_start(message, state)

        mock_intake.clear_session.assert_awaited_once_with(42)

    @pytest.mark.asyncio
    @patch("app.handlers.critical.cleanup_tmp_files", return_value=3)
    @patch("app.handlers.critical.intake_service")
    @patch("app.handlers.critical.main_menu_keyboard")
    async def test_calls_cleanup_tmp_files(
        self,
        _mock_kb,
        mock_intake,
        mock_cleanup,
    ):
        """cmd_start must invoke cleanup_tmp_files with max_age_hours=24."""
        mock_intake.clear_session = AsyncMock()
        state = _make_state()
        message = _make_message()

        await cmd_start(message, state)

        mock_cleanup.assert_called_once_with(max_age_hours=24)

    @pytest.mark.asyncio
    @patch("app.handlers.critical.cleanup_tmp_files", return_value=5)
    @patch("app.handlers.critical.intake_service")
    @patch("app.handlers.critical.main_menu_keyboard")
    async def test_shows_cleanup_count_when_deleted_gt_0(
        self,
        _mock_kb,
        mock_intake,
        _mock_cleanup,
    ):
        """When cleanup deletes files, the count is appended to the message."""
        mock_intake.clear_session = AsyncMock()
        state = _make_state()
        message = _make_message()

        await cmd_start(message, state)

        text = message.answer.call_args[0][0]
        assert "5" in text
        assert "Очищено временных файлов" in text

    @pytest.mark.asyncio
    @patch("app.handlers.critical.cleanup_tmp_files", return_value=0)
    @patch("app.handlers.critical.intake_service")
    @patch("app.handlers.critical.main_menu_keyboard")
    async def test_no_cleanup_message_when_deleted_eq_0(
        self,
        _mock_kb,
        mock_intake,
        _mock_cleanup,
    ):
        """When no files were deleted, no cleanup line appears."""
        mock_intake.clear_session = AsyncMock()
        state = _make_state()
        message = _make_message()

        await cmd_start(message, state)

        text = message.answer.call_args[0][0]
        assert "Очищено временных файлов" not in text


# ---------------------------------------------------------------------------
# /cancel handler
# ---------------------------------------------------------------------------


class TestCmdCancel:
    """Tests for the /cancel command handler."""

    @pytest.mark.asyncio
    @patch("app.handlers.critical.intake_service")
    @patch("app.handlers.critical.main_menu_keyboard")
    async def test_clears_fsm_state(self, _mock_kb, mock_intake):
        """cmd_cancel must clear FSM state."""
        mock_intake.clear_session = AsyncMock()
        state = _make_state()
        message = _make_message()

        await cmd_cancel(message, state)

        state.clear.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.handlers.critical.intake_service")
    @patch("app.handlers.critical.main_menu_keyboard")
    async def test_sends_cancel_confirmation(self, _mock_kb, mock_intake):
        """cmd_cancel must send a cancellation message."""
        mock_intake.clear_session = AsyncMock()
        state = _make_state()
        message = _make_message()

        await cmd_cancel(message, state)

        message.answer.assert_awaited_once()
        text = message.answer.call_args[0][0]
        assert "отменено" in text.lower()

    @pytest.mark.asyncio
    @patch("app.handlers.critical.intake_service")
    @patch("app.handlers.critical.main_menu_keyboard")
    async def test_calls_intake_service_clear_session(
        self, _mock_kb, mock_intake
    ):
        """cmd_cancel must clear the intake session for the current user."""
        mock_intake.clear_session = AsyncMock()
        state = _make_state()
        message = _make_message(user_id=99)

        await cmd_cancel(message, state)

        mock_intake.clear_session.assert_awaited_once_with(99)

    @pytest.mark.asyncio
    @patch("app.handlers.critical.intake_service")
    @patch("app.handlers.critical.main_menu_keyboard")
    async def test_does_not_clear_session_when_no_user(
        self, _mock_kb, mock_intake
    ):
        """When from_user is None, intake_service.clear_session is NOT called."""
        mock_intake.clear_session = AsyncMock()
        state = _make_state()
        message = _make_message(has_user=False)

        await cmd_cancel(message, state)

        mock_intake.clear_session.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("app.handlers.critical.intake_service")
    @patch("app.handlers.critical.main_menu_keyboard")
    async def test_shows_main_menu_keyboard(self, mock_kb, mock_intake):
        """cmd_cancel must reply with the main menu keyboard."""
        mock_intake.clear_session = AsyncMock()
        sentinel_kb = MagicMock(name="keyboard_sentinel")
        mock_kb.return_value = sentinel_kb

        state = _make_state()
        message = _make_message()

        await cmd_cancel(message, state)

        mock_kb.assert_called_once()
        _, kwargs = message.answer.call_args
        assert kwargs["reply_markup"] is sentinel_kb


# ---------------------------------------------------------------------------
# /help handler
# ---------------------------------------------------------------------------


class TestCmdHelp:
    """Tests for the /help command handler."""

    @pytest.mark.asyncio
    @patch("app.handlers.critical.intake_service")
    @patch("app.handlers.critical.main_menu_keyboard")
    async def test_clears_fsm_state(self, _mock_kb, mock_intake):
        """cmd_help must clear FSM state."""
        mock_intake.clear_session = AsyncMock()
        state = _make_state()
        message = _make_message()

        await cmd_help(message, state)

        state.clear.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.handlers.critical.intake_service")
    @patch("app.handlers.critical.main_menu_keyboard")
    async def test_sends_help_text(self, _mock_kb, mock_intake):
        """cmd_help must send a help message with command descriptions."""
        mock_intake.clear_session = AsyncMock()
        state = _make_state()
        message = _make_message()

        await cmd_help(message, state)

        message.answer.assert_awaited_once()
        text = message.answer.call_args[0][0]
        assert "Справка" in text
        assert "/start" in text
        assert "/cancel" in text
        assert "/help" in text

    @pytest.mark.asyncio
    @patch("app.handlers.critical.intake_service")
    @patch("app.handlers.critical.main_menu_keyboard")
    async def test_shows_main_menu_keyboard(self, mock_kb, mock_intake):
        """cmd_help must reply with the main menu keyboard."""
        mock_intake.clear_session = AsyncMock()
        sentinel_kb = MagicMock(name="keyboard_sentinel")
        mock_kb.return_value = sentinel_kb

        state = _make_state()
        message = _make_message()

        await cmd_help(message, state)

        mock_kb.assert_called_once()
        _, kwargs = message.answer.call_args
        assert kwargs["reply_markup"] is sentinel_kb

    @pytest.mark.asyncio
    @patch("app.handlers.critical.intake_service")
    @patch("app.handlers.critical.main_menu_keyboard")
    async def test_calls_intake_service_clear_session(
        self, _mock_kb, mock_intake
    ):
        """cmd_help must clear the intake session for the current user."""
        mock_intake.clear_session = AsyncMock()
        state = _make_state()
        message = _make_message(user_id=777)

        await cmd_help(message, state)

        mock_intake.clear_session.assert_awaited_once_with(777)

    @pytest.mark.asyncio
    @patch("app.handlers.critical.intake_service")
    @patch("app.handlers.critical.main_menu_keyboard")
    async def test_does_not_clear_session_when_no_user(
        self, _mock_kb, mock_intake
    ):
        """When from_user is None, intake_service.clear_session is NOT called."""
        mock_intake.clear_session = AsyncMock()
        state = _make_state()
        message = _make_message(has_user=False)

        await cmd_help(message, state)

        mock_intake.clear_session.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("app.handlers.critical.intake_service")
    @patch("app.handlers.critical.main_menu_keyboard")
    async def test_help_text_contains_button_descriptions(
        self, _mock_kb, mock_intake
    ):
        """cmd_help must describe the keyboard buttons."""
        mock_intake.clear_session = AsyncMock()
        state = _make_state()
        message = _make_message()

        await cmd_help(message, state)

        text = message.answer.call_args[0][0]
        assert "Приход товара" in text
        assert "CRM" in text
        assert "Найти товар" in text
        assert "Статус" in text
