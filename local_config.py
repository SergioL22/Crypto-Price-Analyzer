"""Load a small, literal key=value file without executing or expanding its contents."""
import os
from pathlib import Path

DEFAULT_ENV_PATH = Path(__file__).resolve().parent / '.env'
ALLOWED = frozenset(('TWELVE_DATA_API_KEY', 'OPENAI_API_KEY', 'OPENAI_MODEL'))


def load_local_config(path=None):
    """Existing environment values win, including deliberately empty values.

    Supports blank lines, whole-line comments and optional matching quotes.
    No interpolation, escapes, multiline values or shell syntax are evaluated.
    """
    source = DEFAULT_ENV_PATH if path is None else Path(path)
    try:
        contents = source.read_text(encoding='utf-8-sig')
    except FileNotFoundError:
        return
    except (OSError, UnicodeError):
        raise ValueError('Cannot read local .env configuration. Check its encoding and permissions.') from None
    values = {}
    for line in contents.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        name, separator, value = line.partition('=')
        name, value = name.strip(), value.strip()
        if name not in ALLOWED:
            continue
        if not separator:
            raise ValueError('Invalid local .env configuration: use NAME=value.')
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError('Invalid local .env configuration: unmatched quotes.')
            value = value[1:-1]
        if '\x00' in value:
            raise ValueError('Invalid local .env configuration.')
        if value:
            values[name] = value
    for name, value in values.items():
        os.environ.setdefault(name, value)
