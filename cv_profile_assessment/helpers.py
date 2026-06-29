"""Helper utilities for CV Profile Assessment."""

import json
from pathlib import Path
from typing import Generator, Union


def read_json(path: Union[str, Path]) -> dict:
    """Read and parse a JSON file.
    
    Args:
        path: Path to JSON file.
        
    Returns:
        Parsed JSON as dict.
        
    Raises:
        FileNotFoundError: If file does not exist.
        json.JSONDecodeError: If file contains invalid JSON.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    
    content = path.read_text(encoding="utf-8")
    return json.loads(content)


def write_json(path: Union[str, Path], data: dict, indent: int = 2) -> None:
    """Write data to a JSON file.
    
    Args:
        path: Path to output file.
        data: Data to serialize as JSON.
        indent: JSON indentation level (default: 2).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    content = json.dumps(data, indent=indent, ensure_ascii=False)
    path.write_text(content, encoding="utf-8")


def iter_nonblank_lines(text: str) -> Generator[str, None, None]:
    """Iterate over non-blank lines in text.
    
    Args:
        text: Input text (may contain multiple lines).
        
    Yields:
        Non-blank lines (stripped of surrounding whitespace).
        
    Example:
        >>> text = "line1\\n\\n  \\nline2\\nline3\\n"
        >>> list(iter_nonblank_lines(text))
        ['line1', 'line2', 'line3']
    """
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped:
            yield stripped


def ensure_path(path: Union[str, Path], parent: bool = False) -> Path:
    """Ensure a path exists, creating parent directories if needed.
    
    Args:
        path: Path to ensure exists.
        parent: If True, ensure parent directory exists (for files).
               If False, ensure the path itself exists (for directories).
               
    Returns:
        Path object (absolute).
    """
    path = Path(path).resolve()
    
    if parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    else:
        path.mkdir(parents=True, exist_ok=True)
    
    return path


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """Truncate text to a maximum length.
    
    Args:
        text: Text to truncate.
        max_length: Maximum length (including suffix).
        suffix: Suffix to append when truncated.
        
    Returns:
        Truncated text.
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default on division by zero.
    
    Args:
        numerator: Numerator.
        denominator: Denominator.
        default: Value to return if denominator is zero.
        
    Returns:
        Result of division, or default if denominator is zero.
    """
    if denominator == 0:
        return default
    return numerator / denominator