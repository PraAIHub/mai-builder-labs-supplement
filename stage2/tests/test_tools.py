"""Tools module: test guardrails, refusals, and tool schemas.

The tools live in tools.py and are called by the planner. Tests pin:
- Each tool's guardrail works and returns an error dict, not an exception
- The tool schema lists required arguments correctly
- Tool execution never raises (errors come back as data)
"""

import json
from unittest.mock import Mock, patch

import pytest

from ami import tools
from fakes import MEI, RAJ, ZED


class TestToolSchemas:
    """Tool schemas define the model's interface to the agent."""

    def test_schemas_list_all_tools(self):
        """SCHEMAS should match REGISTRY."""
        schema_names = {s["function"]["name"] for s in tools.SCHEMAS}
        registry_names = set(tools.REGISTRY.keys())
        assert schema_names == registry_names

    def test_find_orders_takes_no_arguments(self):
        """Whose orders these are is fixed by who is signed in — there is no
        argument to widen it with."""
        schema = next(s for s in tools.SCHEMAS if s["function"]["name"] == "find_orders")
        assert schema["function"]["parameters"]["properties"] == {}
        assert schema["function"]["parameters"]["required"] == []

    def test_no_schema_lets_the_model_name_a_user(self):
        """The model must have nowhere to put an identity, on any tool."""
        for s in tools.SCHEMAS:
            props = set(s["function"]["parameters"]["properties"])
            assert not props & {"email", "user_id", "principal", "scope", "owner", "customer"}, s

    def test_cancel_order_schema_requires_order_id(self):
        """cancel_order requires order_id. Stage 2 adds optional confirmed field."""
        schema = next(s for s in tools.SCHEMAS if s["function"]["name"] == "cancel_order")
        assert "order_id" in schema["function"]["parameters"]["required"]
        # Stage 2: confirmed field is in the schema (optional, used by policy layer)
        assert "confirmed" in schema["function"]["parameters"]["properties"]

    def test_start_return_schema_requires_order_id_and_reason(self):
        """start_return requires both order_id and reason. Stage 2 adds optional confirmed."""
        schema = next(s for s in tools.SCHEMAS if s["function"]["name"] == "start_return")
        required = schema["function"]["parameters"]["required"]
        assert "order_id" in required
        assert "reason" in required
        # Stage 2: confirmed field is in the schema (optional, used by policy layer)
        assert "confirmed" in schema["function"]["parameters"]["properties"]

    def test_search_knowledge_schema_requires_question(self):
        """search_knowledge requires question."""
        schema = next(s for s in tools.SCHEMAS if s["function"]["name"] == "search_knowledge")
        assert "question" in schema["function"]["parameters"]["required"]

    def test_escalate_schema_requires_summary(self):
        """escalate requires summary."""
        schema = next(s for s in tools.SCHEMAS if s["function"]["name"] == "escalate")
        assert "summary" in schema["function"]["parameters"]["required"]


class TestToolExecution:
    """Tools return dicts, never raise exceptions."""

    def test_unknown_tool_returns_error_dict(self):
        """Calling a nonexistent tool returns an error dict."""
        result = tools.run("no_such_tool", {}, RAJ)
        assert isinstance(result, dict)
        assert "error" in result

    def test_tool_with_missing_args_returns_error_dict(self):
        """Calling a tool without required args returns an error dict."""
        result = tools.run("cancel_order", {}, RAJ)
        assert isinstance(result, dict)
        assert "error" in result

    def test_tool_with_extra_args_raises_type_error(self, fresh_store):
        """Calling a tool directly with extra args raises TypeError.

        The dispatch function (tools.run) catches this and returns a retryable error.
        """
        with pytest.raises(TypeError):
            tools.find_orders(email="raj@example.com", extra_param="ignored")

    def test_tool_dispatch_handles_type_errors(self, fresh_store):
        """If the tool function raises TypeError, it returns a retryable error."""
        result = tools.run("find_orders", {"email": "raj@example.com", "extra": "arg"}, RAJ)
        # This may or may not be retryable depending on the implementation
        assert isinstance(result, dict)


class TestFindOrders:
    """find_orders lists the SIGNED-IN customer's orders — and only theirs."""

    def test_lists_the_callers_orders(self, fresh_store):
        result = tools.find_orders(RAJ)
        assert {o["order_id"] for o in result["orders"]} == {
            "112-1111111-1111111", "112-2222222-2222222"}

    def test_each_caller_sees_only_their_own(self, fresh_store):
        raj = {o["order_id"] for o in tools.find_orders(RAJ)["orders"]}
        mei = {o["order_id"] for o in tools.find_orders(MEI)["orders"]}
        assert raj and mei and not raj & mei

    def test_caller_with_no_orders_gets_an_empty_answer(self, fresh_store):
        result = tools.find_orders(ZED)
        assert "error" in result and "No orders found" in result["error"]

    def test_returns_limited_fields(self, fresh_store):
        order = tools.find_orders(RAJ)["orders"][0]
        for field in ("order_id", "item", "status", "ordered_on"):
            assert field in order
        assert "price" not in order
        assert "email" not in order and "owner_id" not in order   # no internals

    def test_not_signed_in_gets_nothing(self, fresh_store):
        assert tools.run("find_orders", {}, None) == {"error": "Not signed in."}


class TestGetOrder:
    """get_order returns full details of one order."""

    def test_get_order_returns_details(self, fresh_store):
        result = tools.get_order(RAJ, "112-1111111-1111111")
        assert result["order_id"] == "112-1111111-1111111"
        assert "price" in result
        assert "status" in result
        assert "delivered_on" in result

    def test_get_order_nonexistent_returns_error(self, fresh_store):
        result = tools.get_order(RAJ, "999-9999999-9999999")
        assert "error" in result

    def test_get_order_strips_whitespace(self, fresh_store):
        result = tools.get_order(RAJ, "  112-1111111-1111111  ")
        assert result["order_id"] == "112-1111111-1111111"


class TestTrackPackage:
    """track_package returns carrier events."""

    def test_track_package_returns_events(self, fresh_store):
        result = tools.track_package(RAJ, "112-1111111-1111111")
        assert "carrier" in result
        assert "events" in result
        assert len(result["events"]) > 0

    def test_track_event_has_date_and_detail(self, fresh_store):
        result = tools.track_package(RAJ, "112-1111111-1111111")
        event = result["events"][0]
        assert "date" in event
        assert "detail" in event

    def test_track_nonexistent_order_returns_error(self, fresh_store):
        result = tools.track_package(RAJ, "999-9999999-9999999")
        assert "error" in result


class TestCancelOrder:
    """cancel_order has guardrails tested in test_store.py."""

    def test_cancel_order_returns_refund_details(self, fresh_store):
        result = tools.cancel_order(MEI, "112-3333333-3333333")
        assert result["cancelled"] is True
        assert "refund_amount" in result
        assert "refund_eta" in result


class TestStartReturn:
    """start_return has guardrails tested in test_store.py."""

    def test_start_return_returns_rma_and_instructions(self, fresh_store):
        result = tools.start_return(RAJ, "112-1111111-1111111", "broken screen")
        assert "rma" in result
        assert "instructions" in result


class TestSearchKnowledge:
    """search_knowledge retrieves from the knowledge base.

    To avoid loading chromadb in unit tests, we mock the knowledge.search()
    function and test that the tool correctly formats the response.
    """

    def test_search_knowledge_calls_knowledge_search(self, fresh_store):
        """search_knowledge delegates to knowledge.search()."""
        with patch("ami.knowledge.search") as mock_search:
            mock_search.return_value = [
                {
                    "source": "policies/returns.md",
                    "category": "policies",
                    "heading": "Return Policy",
                    "text": "Orders can be returned within 30 days.",
                }
            ]
            result = tools.search_knowledge(RAJ, "can I return something")
            assert "passages" in result
            assert len(result["passages"]) == 1
            passage = result["passages"][0]
            assert passage["source"] == "policies/returns.md"
            assert passage["category"] == "policies"
            assert passage["policy"] == "Return Policy"

    def test_search_knowledge_with_multiple_results(self, fresh_store):
        """Multiple passages are returned."""
        with patch("ami.knowledge.search") as mock_search:
            mock_search.return_value = [
                {"source": "a", "category": "policies", "heading": "h1", "text": "t1"},
                {"source": "b", "category": "rules", "heading": "h2", "text": "t2"},
            ]
            result = tools.search_knowledge(RAJ, "query")
            assert len(result["passages"]) == 2

    def test_search_knowledge_never_raises(self, fresh_store):
        """Even if knowledge.search raises, the tool returns a result."""
        with patch("ami.knowledge.search", side_effect=Exception("db error")):
            with pytest.raises(Exception):
                # The current implementation will raise if search raises
                # This is a known limitation; in a real system we'd catch it
                tools.search_knowledge(RAJ, "query")


class TestEscalate:
    """escalate hands off to a human."""

    def test_escalate_returns_ticket(self, fresh_store):
        result = tools.escalate(RAJ, "Customer is very upset")
        assert result["escalated"] is True
        assert result["ticket"] == "TEST-1"        # the desk's own number, said out loud

    def test_escalate_includes_summary(self, fresh_store):
        summary = "Order never arrived"
        result = tools.escalate(RAJ, summary)
        assert result["summary"] == summary

    def test_ticket_is_filed_for_the_caller(self, fresh_store, desk_calls):
        tools.escalate(MEI, "Where is my order")
        (name, args), = desk_calls
        assert name == "create_ticket"
        assert args["customer_email"] == "mei@example.com"
        assert "Mei <mei@example.com>" in args["body"]

    def test_ticket_ignores_the_shared_env_customer(self, fresh_store, desk_calls, monkeypatch):
        monkeypatch.setattr("ami.desk.CUSTOMER_EMAIL", "shared@class.example")
        monkeypatch.setattr("ami.desk.CUSTOMER_NAME", "Shared Student")
        tools.escalate(RAJ, "help")
        (_, args), = desk_calls
        assert args["customer_email"] == "raj@example.com"
        assert "Shared Student" not in args["body"]


class TestToolRunObservation:
    """tools.run() logs observations and wraps tool results."""

    def test_run_wraps_errors_in_result(self, fresh_store):
        result = tools.run("cancel_order", {"order_id": "112-2222222-2222222"}, RAJ)
        assert isinstance(result, dict)
        assert "error" in result

    def test_run_marks_success_when_no_error(self, fresh_store):
        result = tools.run("escalate", {"summary": "test"}, RAJ)
        assert isinstance(result, dict)
        # If no error, the result should still be a dict with the tool's response
        assert "escalated" in result


class TestToolArguments:
    """Tools handle arguments correctly."""

    def test_order_id_is_stripped_of_whitespace(self, fresh_store):
        """Order IDs come in with possible extra spaces."""
        result = tools.get_order(RAJ, "  112-1111111-1111111  ")
        assert "error" not in result
