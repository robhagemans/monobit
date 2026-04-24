"""
monobit.storage.pathutils - container and path helpers

(c) 2019--2026 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

from pathlib import Path
from collections import deque

from .magic import iter_funcs_from_registry


def _contains(container, path, match_case):
    """Container contains file (case insensitive)."""
    _, tail = _match_path(container, path, match_case)
    return tail == Path('.')


def _match(container, path, match_case):
    """Container contains file (case insensitive)."""
    head, tail = _match_path(container, path, match_case)
    if tail == Path('.'):
        return head
    raise FileNotFoundError(
        f"'{path}' not found on {container} "
        f"with case-{'' if match_case else 'in'}sensitive match."
    )


def _match_path(container, path, match_case):
    """Stepwise match per path element."""
    segments = Path(path).as_posix().split('/')
    segments = deque(segments)
    matched_path = Path('.')
    while True:
        target = segments.popleft()
        # drop empty elements (repeated/initial slashes)
        if not target:
            continue
        # try case-sensitive match first, then case-insensitive
        match = _step_match(container, matched_path, target, match_case=True)
        if not match and not match_case:
            match = _step_match(container, matched_path, target, match_case=False)
        if match:
            matched_path /= match
            if not segments or not container.is_dir(matched_path):
                # found match this level, can't go deeper
                return matched_path, Path(*segments)
            # found match this level, go to next
            continue
        # no match this level
        return matched_path, Path(target, *segments)


def _step_match(container, matched_path, target, match_case):
    """One-step match for path element."""
    target = str(target)
    for name in container.iter_sub(matched_path):
        found = Path(name).name
        if (found == target) or (
                (not match_case)
                and found.lower() == target.lower()
            ):
            return found
    return ''
