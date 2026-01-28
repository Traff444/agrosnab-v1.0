"""Tests for AI manager."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestBuildTools:
    """Tests for build_tools() function."""

    def test_returns_list(self):
        from app.ai_manager import build_tools

        tools = build_tools()
        assert isinstance(tools, list)

    def test_has_five_tools(self):
        from app.ai_manager import build_tools

        tools = build_tools()
        assert len(tools) == 5

    def test_tool_structure(self):
        from app.ai_manager import build_tools

        tools = build_tools()
        for tool in tools:
            assert "type" in tool
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]

    def test_tool_names(self):
        from app.ai_manager import build_tools

        tools = build_tools()
        names = [t["function"]["name"] for t in tools]
        assert "search_products" in names
        assert "add_to_cart" in names
        assert "show_cart" in names
        assert "checkout_hint" in names
        assert "list_all_products" in names

    def test_add_to_cart_parameters(self):
        from app.ai_manager import build_tools

        tools = build_tools()
        add_to_cart = next(t for t in tools if t["function"]["name"] == "add_to_cart")
        params = add_to_cart["function"]["parameters"]

        assert "properties" in params
        assert "sku" in params["properties"]
        assert "qty" in params["properties"]
        assert params["properties"]["qty"]["type"] == "integer"
        assert "required" in params
        assert "sku" in params["required"]
        assert "qty" in params["required"]

    def test_search_products_parameters(self):
        from app.ai_manager import build_tools

        tools = build_tools()
        search = next(t for t in tools if t["function"]["name"] == "search_products")
        params = search["function"]["parameters"]

        assert "query" in params["properties"]
        assert "query" in params["required"]


class TestSystemPrompt:
    """Tests for SYSTEM_PROMPT constant."""

    def test_prompt_exists(self):
        from app.ai_manager import SYSTEM_PROMPT

        assert SYSTEM_PROMPT
        assert len(SYSTEM_PROMPT) > 100

    def test_prompt_contains_critical_instructions(self):
        from app.ai_manager import SYSTEM_PROMPT

        assert "list_all_products" in SYSTEM_PROMPT
        assert "SKU" in SYSTEM_PROMPT
        assert "add_to_cart" in SYSTEM_PROMPT


class TestRunAi:
    """Tests for run_ai() function."""

    @pytest.fixture
    def mock_openai_client(self):
        """Create mock OpenAI client."""
        with patch("app.ai_manager.AsyncOpenAI") as mock_class:
            mock_client = AsyncMock()
            mock_class.return_value = mock_client
            yield mock_client

    @pytest.fixture
    def sample_tool_impl(self):
        """Sample tool implementations."""

        async def search_products(args):
            return {"products": [{"sku": "PRD-001", "name": "Test Product"}]}

        async def add_to_cart(args):
            return {"success": True, "message": "Added to cart"}

        async def show_cart(args):
            return {"items": [], "total": 0}

        async def checkout_hint(args):
            return {"hint": "Please provide your phone number"}

        async def list_all_products(args):
            return {"products": [{"sku": "PRD-001", "name": "Test", "price": 100}]}

        return {
            "search_products": search_products,
            "add_to_cart": add_to_cart,
            "show_cart": show_cart,
            "checkout_hint": checkout_hint,
            "list_all_products": list_all_products,
        }

    @pytest.mark.asyncio
    async def test_simple_response_no_tools(self, mock_openai_client, sample_tool_impl):
        """Test simple response without tool calls."""
        from app.ai_manager import run_ai

        # Mock response without tool calls
        mock_message = MagicMock()
        mock_message.tool_calls = None
        mock_message.content = "Hello! How can I help you?"

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await run_ai(
            api_key="test-key",
            model="gpt-4",
            user_text="Hello",
            tool_impl=sample_tool_impl,
        )

        assert result["text"] == "Hello! How can I help you?"

    @pytest.mark.asyncio
    async def test_response_with_tool_call(self, mock_openai_client, sample_tool_impl):
        """Test response that includes a tool call."""
        from app.ai_manager import run_ai

        # First response with tool call
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "list_all_products"
        mock_tool_call.function.arguments = "{}"

        mock_message1 = MagicMock()
        mock_message1.tool_calls = [mock_tool_call]
        mock_message1.content = None

        mock_choice1 = MagicMock()
        mock_choice1.message = mock_message1

        mock_response1 = MagicMock()
        mock_response1.choices = [mock_choice1]

        # Second response without tool call (final answer)
        mock_message2 = MagicMock()
        mock_message2.tool_calls = None
        mock_message2.content = "Here are the products!"

        mock_choice2 = MagicMock()
        mock_choice2.message = mock_message2

        mock_response2 = MagicMock()
        mock_response2.choices = [mock_choice2]

        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=[mock_response1, mock_response2]
        )

        result = await run_ai(
            api_key="test-key",
            model="gpt-4",
            user_text="What products do you have?",
            tool_impl=sample_tool_impl,
        )

        assert result["text"] == "Here are the products!"
        assert mock_openai_client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_response_with_add_to_cart_tool(self, mock_openai_client, sample_tool_impl):
        """Test add_to_cart tool execution."""
        from app.ai_manager import run_ai

        # Tool call with arguments
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_456"
        mock_tool_call.function.name = "add_to_cart"
        mock_tool_call.function.arguments = json.dumps({"sku": "PRD-001", "qty": 5})

        mock_message1 = MagicMock()
        mock_message1.tool_calls = [mock_tool_call]
        mock_message1.content = None

        mock_choice1 = MagicMock()
        mock_choice1.message = mock_message1

        mock_response1 = MagicMock()
        mock_response1.choices = [mock_choice1]

        mock_message2 = MagicMock()
        mock_message2.tool_calls = None
        mock_message2.content = "Added 5 items to cart!"

        mock_choice2 = MagicMock()
        mock_choice2.message = mock_message2

        mock_response2 = MagicMock()
        mock_response2.choices = [mock_choice2]

        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=[mock_response1, mock_response2]
        )

        result = await run_ai(
            api_key="test-key",
            model="gpt-4",
            user_text="Add 5 items",
            tool_impl=sample_tool_impl,
        )

        assert result["text"] == "Added 5 items to cart!"

    @pytest.mark.asyncio
    async def test_unknown_tool_handling(self, mock_openai_client, sample_tool_impl):
        """Test handling of unknown tool name."""
        from app.ai_manager import run_ai

        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_789"
        mock_tool_call.function.name = "unknown_tool"
        mock_tool_call.function.arguments = "{}"

        mock_message1 = MagicMock()
        mock_message1.tool_calls = [mock_tool_call]
        mock_message1.content = None

        mock_choice1 = MagicMock()
        mock_choice1.message = mock_message1

        mock_response1 = MagicMock()
        mock_response1.choices = [mock_choice1]

        mock_message2 = MagicMock()
        mock_message2.tool_calls = None
        mock_message2.content = "Sorry, I encountered an error."

        mock_choice2 = MagicMock()
        mock_choice2.message = mock_message2

        mock_response2 = MagicMock()
        mock_response2.choices = [mock_choice2]

        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=[mock_response1, mock_response2]
        )

        result = await run_ai(
            api_key="test-key",
            model="gpt-4",
            user_text="Do something",
            tool_impl=sample_tool_impl,
        )

        # Should still return a response
        assert "text" in result

    @pytest.mark.asyncio
    async def test_invalid_json_arguments(self, mock_openai_client, sample_tool_impl):
        """Test handling of invalid JSON in tool arguments."""
        from app.ai_manager import run_ai

        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_invalid"
        mock_tool_call.function.name = "search_products"
        mock_tool_call.function.arguments = "invalid json {"

        mock_message1 = MagicMock()
        mock_message1.tool_calls = [mock_tool_call]
        mock_message1.content = None

        mock_choice1 = MagicMock()
        mock_choice1.message = mock_message1

        mock_response1 = MagicMock()
        mock_response1.choices = [mock_choice1]

        mock_message2 = MagicMock()
        mock_message2.tool_calls = None
        mock_message2.content = "I searched for products."

        mock_choice2 = MagicMock()
        mock_choice2.message = mock_message2

        mock_response2 = MagicMock()
        mock_response2.choices = [mock_choice2]

        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=[mock_response1, mock_response2]
        )

        result = await run_ai(
            api_key="test-key",
            model="gpt-4",
            user_text="Search",
            tool_impl=sample_tool_impl,
        )

        assert "text" in result

    @pytest.mark.asyncio
    async def test_max_iterations_limit(self, mock_openai_client, sample_tool_impl):
        """Test that max iterations limit is enforced."""
        from app.ai_manager import run_ai

        # Always return tool calls to trigger max iterations
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_loop"
        mock_tool_call.function.name = "list_all_products"
        mock_tool_call.function.arguments = "{}"

        mock_message = MagicMock()
        mock_message.tool_calls = [mock_tool_call]
        mock_message.content = None

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await run_ai(
            api_key="test-key",
            model="gpt-4",
            user_text="Loop forever",
            tool_impl=sample_tool_impl,
        )

        assert "лимит" in result["text"].lower()
        # Should have called 5 times (max_iterations)
        assert mock_openai_client.chat.completions.create.call_count == 5

    @pytest.mark.asyncio
    async def test_api_error_handling(self, mock_openai_client, sample_tool_impl):
        """Test handling of API errors."""
        from app.ai_manager import run_ai

        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=Exception("API Error")
        )

        result = await run_ai(
            api_key="test-key",
            model="gpt-4",
            user_text="Hello",
            tool_impl=sample_tool_impl,
        )

        assert "Ошибка AI" in result["text"]
        assert "API Error" in result["text"]

    @pytest.mark.asyncio
    async def test_with_history(self, mock_openai_client, sample_tool_impl):
        """Test that history is included in messages."""
        from app.ai_manager import run_ai

        mock_message = MagicMock()
        mock_message.tool_calls = None
        mock_message.content = "Response with history"

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ]

        result = await run_ai(
            api_key="test-key",
            model="gpt-4",
            user_text="New question",
            tool_impl=sample_tool_impl,
            history=history,
        )

        assert result["text"] == "Response with history"

        # Check that history was included in the call
        call_args = mock_openai_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]

        # Should have: system + 2 history + 1 new = 4 messages
        assert len(messages) == 4
        assert messages[0]["role"] == "system"
        assert messages[1]["content"] == "Previous question"
        assert messages[2]["content"] == "Previous answer"
        assert messages[3]["content"] == "New question"

    @pytest.mark.asyncio
    async def test_empty_content_response(self, mock_openai_client, sample_tool_impl):
        """Test handling of empty content in response."""
        from app.ai_manager import run_ai

        mock_message = MagicMock()
        mock_message.tool_calls = None
        mock_message.content = None

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await run_ai(
            api_key="test-key",
            model="gpt-4",
            user_text="Hello",
            tool_impl=sample_tool_impl,
        )

        assert result["text"] == ""

    @pytest.mark.asyncio
    async def test_multiple_tool_calls(self, mock_openai_client, sample_tool_impl):
        """Test handling of multiple tool calls in single response."""
        from app.ai_manager import run_ai

        mock_tool_call1 = MagicMock()
        mock_tool_call1.id = "call_1"
        mock_tool_call1.function.name = "list_all_products"
        mock_tool_call1.function.arguments = "{}"

        mock_tool_call2 = MagicMock()
        mock_tool_call2.id = "call_2"
        mock_tool_call2.function.name = "show_cart"
        mock_tool_call2.function.arguments = "{}"

        mock_message1 = MagicMock()
        mock_message1.tool_calls = [mock_tool_call1, mock_tool_call2]
        mock_message1.content = None

        mock_choice1 = MagicMock()
        mock_choice1.message = mock_message1

        mock_response1 = MagicMock()
        mock_response1.choices = [mock_choice1]

        mock_message2 = MagicMock()
        mock_message2.tool_calls = None
        mock_message2.content = "Here are products and your cart!"

        mock_choice2 = MagicMock()
        mock_choice2.message = mock_message2

        mock_response2 = MagicMock()
        mock_response2.choices = [mock_choice2]

        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=[mock_response1, mock_response2]
        )

        result = await run_ai(
            api_key="test-key",
            model="gpt-4",
            user_text="Show me products and my cart",
            tool_impl=sample_tool_impl,
        )

        assert result["text"] == "Here are products and your cart!"

    @pytest.mark.asyncio
    async def test_tool_arguments_none(self, mock_openai_client, sample_tool_impl):
        """Test handling of None tool arguments."""
        from app.ai_manager import run_ai

        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_none_args"
        mock_tool_call.function.name = "show_cart"
        mock_tool_call.function.arguments = None

        mock_message1 = MagicMock()
        mock_message1.tool_calls = [mock_tool_call]
        mock_message1.content = None

        mock_choice1 = MagicMock()
        mock_choice1.message = mock_message1

        mock_response1 = MagicMock()
        mock_response1.choices = [mock_choice1]

        mock_message2 = MagicMock()
        mock_message2.tool_calls = None
        mock_message2.content = "Your cart is empty"

        mock_choice2 = MagicMock()
        mock_choice2.message = mock_message2

        mock_response2 = MagicMock()
        mock_response2.choices = [mock_choice2]

        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=[mock_response1, mock_response2]
        )

        result = await run_ai(
            api_key="test-key",
            model="gpt-4",
            user_text="Show cart",
            tool_impl=sample_tool_impl,
        )

        assert result["text"] == "Your cart is empty"


class TestOpenAITimeout:
    """Tests for OPENAI_TIMEOUT constant."""

    def test_timeout_configured(self):
        from app.ai_manager import OPENAI_TIMEOUT

        assert OPENAI_TIMEOUT.read == 60.0
        assert OPENAI_TIMEOUT.connect == 10.0
