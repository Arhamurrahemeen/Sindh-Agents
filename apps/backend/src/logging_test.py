import json
import logging
import sys

from src.logging import JsonFormatter


def test_formats_basic_record_as_json() -> None:
    record = logging.LogRecord("test", logging.INFO, "path", 1, "hello", None, None)
    parsed = json.loads(JsonFormatter().format(record))
    assert parsed["message"] == "hello"
    assert parsed["level"] == "info"
    assert "exception" not in parsed


def test_includes_traceback_when_exception_present() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord("test", logging.ERROR, "path", 1, "failed", None, sys.exc_info())
    parsed = json.loads(JsonFormatter().format(record))
    assert "ValueError: boom" in parsed["exception"]
