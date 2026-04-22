import logging

from utils.logging import setup_logging


def test_setup_logging_default():
    # Ensure deterministic state
    logging.getLogger().handlers.clear()
    setup_logging(verbose=False)
    root = logging.getLogger()
    assert root.level == logging.WARNING
    main_logger = logging.getLogger("__main__")
    assert main_logger.level == logging.INFO or main_logger.level == 0


def test_setup_logging_verbose():
    logging.getLogger().handlers.clear()
    setup_logging(verbose=True)
    root = logging.getLogger()
    assert root.level <= logging.DEBUG


def test_setup_logging_idempotent():
    logging.getLogger().handlers.clear()
    setup_logging(verbose=False)
    # Call again with different verbosity
    setup_logging(verbose=True)
    # Ensure handlers not duplicated
    handlers = logging.getLogger().handlers
    assert len(handlers) == 1
