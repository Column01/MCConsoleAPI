import logging
import sys


def get_logger(name: str) -> logging.Logger:
    # Configure logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    # Check if the logger already has a formatter
    if len(logger.handlers) == 0:
        stream_handler = logging.StreamHandler()
        log_formatter = logging.Formatter("%(levelname)s:     %(name)s: %(message)s")
        stream_handler.setFormatter(log_formatter)
        logger.addHandler(stream_handler)
    return logger
