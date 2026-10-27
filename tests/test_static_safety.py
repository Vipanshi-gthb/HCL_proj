"""Static safety checks verifying no unsafe code execution or dynamic execution in src/."""

import os
import re
import pytest

BANNED_PATTERNS = [
    r"\bexec\s*\(",
    r"\beval\s*\(",
    r"\bcompile\s*\(",
    r"\b__import__\s*\(",
    r"\bpickle\b",
    r"\bsubprocess\b",
    r"\bos\.system\b",
    r"\bgetattr\s*\(",
]


def test_no_banned_functions_in_src():
    src_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))
    assert os.path.isdir(src_dir), f"src directory not found at {src_dir}"

    violations = []

    for root, _, files in os.walk(src_dir):
        for file in files:
            if not file.endswith(".py"):
                continue
            file_path = os.path.join(root, file)
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            in_docstring = False
            for line_no, line in enumerate(lines, 1):
                stripped = line.strip()

                # Multi-line docstring tracking
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    if stripped.count('"""') == 1 or stripped.count("'''") == 1:
                        in_docstring = not in_docstring
                        continue
                    elif stripped.count('"""') >= 2 or stripped.count("'''") >= 2:
                        continue

                if in_docstring or stripped.startswith("#"):
                    continue

                for pattern in BANNED_PATTERNS:
                    if re.search(pattern, line):
                        violations.append(f"{file}:{line_no}: pattern '{pattern}' found in: {stripped}")

    assert not violations, f"Security violations found in src/:\n" + "\n".join(violations)
