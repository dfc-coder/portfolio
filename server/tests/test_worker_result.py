from app.worker import _final_answer


def test_worker_wraps_plain_model_text() -> None:
    assert _final_answer("Mañana será jueves.") == "Mañana será jueves."


def test_worker_keeps_legacy_json_answer_compatible() -> None:
    assert _final_answer('{"answer":"Hola."}') == "Hola."
