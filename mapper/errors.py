"""Custom errors for the mapper (course-provided; do not modify)."""

from typing import Iterable


class UnsupportedQueryError(Exception):
    """Raised when a question does not match any of the canonical shapes.

    The message names every supported shape so the failure is fail-loud
    and the engineering exercise of adding the next template is
    discoverable from the error alone.
    """

    SHAPE_DESCRIPTIONS = {
        "q1":  "Find recipes that use <ingredient>",
        "q2":  "Find recipes by author <name>",
        "q3":  "Find <cuisine> recipes",
        "q4":  "Find recipes in a cuisine and all subtypes (e.g., 'Asian recipes')",
        "q5":  "Find <cuisine> recipes that use <ingredient>",
        "q6":  "Find recipes in a cuisine subtree that use <ingredient>",
        "q7":  "Find recipes that require <technique> technique",
        "q8":  "Find recipes by author <name> that use <ingredient>",
        "q9":  "Find <cuisine> recipes ranked by popularity",
        "q10": "Find recipes with prep time under <N> minutes",
        "q11": "Find ingredients used in <cuisine> recipes",
        "q12": "Find authors of <cuisine> recipes (including subtypes)",
        "q13": "Find recipes that use <ingredient> or any subtype",
        "q14": "Find recipes that use <ingredient> but not <other-ingredient>",
        "q15": "Find recipes optionally tagged with <technique>",
        "q16": "Find recipes by author <name> that require <technique>",
        "q17": "Find <cuisine> recipes that use <technique>",
        "q18": "Find <cuisine> recipes by author <name>",
        "q19": "Find <cuisine> recipes by author <name> that use <ingredient>",
        "q20": "Find ingredients used by author <name>"
    }

    def __init__(self, question_text: str, shape_names: Iterable[str] | None = None):
        names = list(shape_names) if shape_names is not None else list(self.SHAPE_DESCRIPTIONS)
        lines = [f"  - {n}: {self.SHAPE_DESCRIPTIONS.get(n, '(no description)')}" for n in names]
        msg = (
            f"Question shape not supported: {question_text!r}\n"
            f"Supported shapes:\n" + "\n".join(lines)
        )
        super().__init__(msg)
        self.question_text = question_text
        self.shape_names = names
