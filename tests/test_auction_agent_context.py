from src.auction_agent_context import append_agent_context, format_agent_context


def test_agent_context_is_bounded_and_formatted():
    messages = []
    for number in range(10):
        messages = append_agent_context(messages, "note {0}".format(number))

    assert messages == ["note {0}".format(number) for number in range(2, 10)]
    assert "Manager context: note 2" in format_agent_context(messages)
    assert "Manager context: note 9" in format_agent_context(messages)


def test_empty_agent_context_is_ignored():
    assert append_agent_context(["keep"], "   ") == ["keep"]
