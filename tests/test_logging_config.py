import logging
import os
import tempfile
from secmap.logging_config import configure_logging


def test_console_logging_configures_root():
    configure_logging("DEBUG")
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert any(isinstance(h, logging.StreamHandler) for h in root.handlers)


def test_file_logging():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "secmap.log")
        configure_logging("INFO", log_file=path)

        logger = logging.getLogger("test")
        logger.info("hello")

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "hello" in content

        # Close file handlers so Windows can clean up the temp directory
        root = logging.getLogger()
        for h in list(root.handlers):
            if isinstance(h, logging.FileHandler):
                h.close()
                root.removeHandler(h)


def test_no_duplicate_handlers():
    configure_logging("INFO")
    first_count = len(logging.getLogger().handlers)

    configure_logging("INFO")
    second_count = len(logging.getLogger().handlers)

    assert first_count == second_count
