from meeting_bridge.ux_logic import readiness_summary, should_suggest_topic_shift


def test_readiness_summary_ready():
    ready, text = readiness_summary(
        mic_ready=True,
        speaker_ready=True,
        model_ready=True,
        ai_ready=True,
    )
    assert ready is True
    assert "Готов к работе" in text


def test_readiness_summary_lists_only_missing_parts():
    ready, text = readiness_summary(
        mic_ready=True,
        speaker_ready=False,
        model_ready=True,
        ai_ready=False,
    )
    assert ready is False
    assert "звук собеседника" in text
    assert "доступ к ИИ" in text
    assert "микрофон" not in text


def test_topic_shift_is_conservative():
    assert should_suggest_topic_shift({"accounting"}, {"requirements"}) is True
    assert should_suggest_topic_shift({"accounting"}, {"accounting", "diagnosis"}) is False
    assert should_suggest_topic_shift(set(), {"accounting"}) is False
