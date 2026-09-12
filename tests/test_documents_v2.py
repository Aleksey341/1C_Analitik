from meeting_bridge.documents_v2 import extract_protocol_sections


def test_1c_protocol_detects_accounting_and_month_close():
    rows = [
        ("10:00:00", "Собеседник", "Почему после закрытия месяца остался остаток на 25 счете?"),
        ("10:00:10", "Я", "Нужно проверить распределение затрат и сверить себестоимость."),
        ("10:00:20", "Я", "Решили сначала проверить движения документа и затем согласовать исправление."),
    ]
    result = extract_protocol_sections(rows)
    assert "Закрытие месяца и себестоимость" in result["agenda"]
    assert result["actions"]
    assert result["decisions"]
    assert result["questions"]


def test_protocol_excludes_ai_from_human_agenda_source():
    rows = [
        ("10:00:00", "ИИ", "Нужно проверить НДС и книгу продаж."),
        ("10:00:05", "Собеседник", "Обсудим настройки прав пользователя."),
    ]
    result = extract_protocol_sections(rows)
    assert "Права / ЭДО / интеграции" in result["agenda"]
    assert "НДС" not in result["agenda"]
