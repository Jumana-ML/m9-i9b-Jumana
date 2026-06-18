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
    hierarchical_cuisines = {"asian", "chinese"}
    direct_cuisines = {"italian", "sichuan"}
    techniques_list = {"wok", "baking", "roasting", "grilling", "technique", "require"}
    
    # Check for core entities/keywords presence
    has_author_cue = "by author" in q or ("by " in q and "popularity" not in q and "ranked" not in q) or "authors of" in q
    
    has_ingredient_cue = ("use" in q or "with" in q) and not any(t in q for t in ["baking", "roasting", "grilling", "ingredients used in"])
    
    has_cuisine_cue = any(c in q for c in (hierarchical_cuisines | direct_cuisines))
    has_technique_cue = any(t in q for t in techniques_list) or "tagged with" in q
    # 2. Apply rules in priority order (Specific -> General)

    # Q14: Negation (but not) - Must be before Q1/Q5/Q6/Q8/Q19
    if "but not" in q or "without" in q:
        return ShapeId.Q14
    
    # Q11: Inverse - Ingredients used in [Cuisine]
    if "ingredients used in" in q:
        return ShapeId.Q11

    # Q12: Inverse - Authors of [Cuisine]
    if "authors of" in q:
        return ShapeId.Q12
        
    # Q20 (Tier 1): Ingredients by specific Author
    if "ingredients by" in q:
        return ShapeId.Q20

    # Q9: Sorting (Popularity)
    if "ranked by popularity" in q or "most popular" in q:
        return ShapeId.Q9

    # Q19 (Tier 1): Triple Conjunction (Cuisine + Author + Ingredient)
    if has_cuisine_cue and has_author_cue and has_ingredient_cue:
        return ShapeId.Q19

    # Q8: Conjunction (Author + Ingredient)
    if has_author_cue and has_ingredient_cue:
        return ShapeId.Q8

    # Q18 (Tier 1): Conjunction (Cuisine + Author)
    if has_cuisine_cue and has_author_cue:
        return ShapeId.Q18

    # Q16 (Tier 1): Conjunction (Author + Technique)
    if has_author_cue and has_technique_cue:
        return ShapeId.Q16

    # Q17 (Tier 1): Conjunction (Cuisine + Technique)
    if has_cuisine_cue and has_technique_cue:
        return ShapeId.Q17

    # Q6: Conjunction (Hierarchical)
    if any(hc in q for hc in hierarchical_cuisines) and has_ingredient_cue:
        return ShapeId.Q6

    # Q5: Conjunction (Direct)
    if any(dc in q for dc in direct_cuisines) and has_ingredient_cue:
        return ShapeId.Q5

    # Q15: Optional tagging
    if "optionally tagged" in q:
        return ShapeId.Q15

    # Q13: Ingredient hierarchy (subtype/kind)
    if "or any subtype" in q or "or any kind" in q:
        return ShapeId.Q13

    # Q10: Property filter (Time)
    if "under" in q and "minutes" in q:
        return ShapeId.Q10

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