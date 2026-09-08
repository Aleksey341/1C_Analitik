from meeting_bridge.ai_reader import latest_ai_reply


def test_latest_ai_reply_returns_newest_ai_block_without_prefix() -> None:
    blocks = [
        "[10:00:00] Я: Первый вопрос",
        "[10:00:05] ИИ: Первый ответ",
        "[10:00:10] Собеседник: Продолжаем разговор",
        "[10:00:15] ИИ: Второй ответ\nсо второй строкой",
        "[10:00:20] Я: Новая реплика",
    ]

    assert latest_ai_reply(blocks) == "Второй ответ\nсо второй строкой"


def test_latest_ai_reply_returns_empty_when_no_ai_blocks() -> None:
    assert latest_ai_reply(["[10:00:00] Я: Вопрос"]) == ""
