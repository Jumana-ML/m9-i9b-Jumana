"""Intent classifier — map NL question to a canonical ShapeId.

This file is your responsibility. Read the 15 supported shapes in
`shapes.ShapeId` and `shapes.CANONICAL_CYPHER`, then implement
`detect_shape` so that each of the 15 canonical eval questions in
`data/eval_questions.jsonl` is classified to the gold shape, and
adversarial / off-template questions return None.

The deterministic mapper is the production-discipline arm of M9B; a
classifier that returns the wrong shape on a supported question is a
real bug, and a classifier that returns a confident answer on an
off-template question is the silent-failure mode the Reading warns
against. Prefer None over a false positive.
"""

from .shapes import ShapeId


def detect_shape(question: str) -> ShapeId | None:
    """Classify the question into one of the 15 ShapeId values, or None.

    Suggested approach: a small set of keyword / regex rules over the
    question text that match the shape vocabulary used by the recipe
    KG. Look for cues such as:
      - "by author <name>", "by <Name>"   → author shapes
      - "<cuisine name>"                  → cuisine shapes
      - "use <ingredient>", "with <ingredient>" → ingredient shapes
      - "but not <ingredient>"            → q14 (negation)
      - "ranked by popularity" / "most popular" → q9
      - "under <N> minutes"               → q10
      - "ingredients used in"             → q11 (inverse)
      - "authors of"                      → q12
      - "or any subtype" / "or any kind"  → q13
      - "optionally tagged"               → q15
      - "require <technique>"             → q7

    For cuisines and ingredients, you can use the schema label vocabulary
    (Cuisine.name values, Ingredient.name values) to disambiguate which
    slot type the question is naming. A spaCy NER pass on PERSON entities
    helps for q2 / q8.

    Returns None when no rule fires — the orchestrator raises
    UnsupportedQueryError in that case, which is the correct behaviour
    for an out-of-scope question.
    """
    # 1. Lowercase the question for pattern matching.
    q = question.lower()

    # Define vocabulary hints based on the Integration Guide
    # These help distinguish between direct and hierarchical queries
    hierarchical_cuisines = {"asian", "chinese"}
    direct_cuisines = {"italian", "sichuan"} # Sichuan is direct in Q5 but hierarchical in Q12/Q4 context
    
    # Check for core entities/keywords presence
    has_author_cue = "by author" in q or "by " in q or "authors of" in q
    has_ingredient_cue = "use" in q or "with" in q
    has_cuisine_cue = any(c in q for c in (hierarchical_cuisines | direct_cuisines))
    has_technique_cue = "require" in q or "tagged with" in q or "technique" in q

    # 2. Apply rules in priority order (Specific -> General)

    # Q14: Negation (but not) - Must be before Q1/Q5/Q6/Q8
    if "but not" in q or "without" in q:
        return ShapeId.Q14

    # Q15: Optional tagging
    if "optionally tagged" in q:
        return ShapeId.Q15

    # Q13: Ingredient hierarchy (subtype/kind)
    if "or any subtype" in q or "or any kind" in q:
        return ShapeId.Q13

    # Q11: Inverse - Ingredients used in [Cuisine]
    if "ingredients used in" in q:
        return ShapeId.Q11

    # Q12: Inverse - Authors of [Cuisine]
    if "authors of" in q:
        return ShapeId.Q12

    # Q9: Sorting (Popularity)
    if "ranked by popularity" in q or "most popular" in q:
        return ShapeId.Q9

    # Q10: Property filter (Time)
    if "under" in q and "minutes" in q:
        return ShapeId.Q10

    # Q8: Conjunction (Author + Ingredient) - Must be before Q2
    if has_author_cue and has_ingredient_cue:
        return ShapeId.Q8

    # Q6: Conjunction (Hierarchical Cuisine + Ingredient) - e.g., "Chinese recipes that use..."
    if any(hc in q for hc in hierarchical_cuisines) and has_ingredient_cue:
        return ShapeId.Q6

    # Q5: Conjunction (Direct Cuisine + Ingredient) - e.g., "Sichuan recipes that use..."
    if any(dc in q for dc in direct_cuisines) and has_ingredient_cue:
        return ShapeId.Q5

    # Q7: Technique
    if "require" in q or has_technique_cue:
        return ShapeId.Q7

    # Q4: Hierarchical Cuisine only
    if any(hc in q for hc in hierarchical_cuisines):
        return ShapeId.Q4

    # Q3: Direct Cuisine only
    if any(dc in q for dc in direct_cuisines):
        return ShapeId.Q3

    # Q2: Author only
    if has_author_cue:
        return ShapeId.Q2

    # Q1: Ingredient only
    if has_ingredient_cue:
        return ShapeId.Q1

    # 3. Return None if nothing matches
    return None