"""cv-profile-assessment package — language-aware CV parsing & matching."""

from .language_detection import detect_language
from .usage_history import log_processing_run, read_history, format_history_table

__version__ = "0.2.0"
__all__ = [
    "detect_language",
    "log_processing_run",
    "read_history",
    "format_history_table",
]
