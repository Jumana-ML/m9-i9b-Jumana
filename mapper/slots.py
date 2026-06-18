"""Slot extraction — fill the named slots a shape's Cypher template needs.

Each shape in `shapes.CANONICAL_CYPHER` carries `$param` placeholders.
Your `extract_slots(question, shape)` returns a dict whose keys are the
parameter names the template expects, e.g.:

  ShapeId.Q1 → {"ingredient": "ginger"}
  ShapeId.Q5 → {"cuisine": "Sichuan", "ingredient": "ginger"}
  ShapeId.Q9 → {"cuisine": "Italian"}
  ShapeId.Q10 → {"max_minutes": 30}
  ShapeId.Q14 → {"ingredient": "ginger", "exclude_ingredient": "garlic"}

See `data/eval_questions.jsonl` for the gold (question_text, shape, slots)
triples used by the autograder.
"""

import re
import spacy
from .shapes import ShapeId

# Load spaCy model for NER (PERSON entities)
try:
    nlp = spacy.load("en_core_web_sm")
except ImportError:
    # Fallback if model not loaded in this environment yet
    nlp = None

# Canonical Vocabulary lists from the KG schema
CUISINES = ["Italian", "Sichuan", "Chinese", "Asian", "Mexican", "French", "Japanese", "Mediterranean", "World"]
INGREDIENTS = ["ginger", "garlic", "basil", "peppercorn", "tomato", "chicken", "soy sauce", "salt"]
TECHNIQUES = ["wok", "roasting", "baking", "grilling"]


def extract_slots(question: str, shape: ShapeId) -> dict:
    """Extract slot values for the given shape from the question text.

    Suggested approach:
      - spaCy NER for PERSON entities (q2, q8 author slot).
      - A short hand-authored vocabulary list of the cuisines and
        ingredients in the recipe KG — string-match the question against
        it case-insensitively. The lists are small (16 cuisines, 40
        ingredients) so a literal-match approach is fine.
      - For q10: a regex like `under (\\d+)\\s*minutes` to pull the
        integer threshold.
      - For q14: split the question on "but not" / "without" to get the
        positive and negative ingredient slots.

    Return a dict whose keys EXACTLY match the `$param` names in
    shapes.CANONICAL_CYPHER[shape]. Returning a slot dict missing a
    required parameter will surface as a Neo4j ParameterMissing error
    at query time — that is fail-loud and desired.

    Values must be the canonical form the KG uses (e.g., 'Italian' not
    'italian'; 'ginger' not 'Ginger'). Match against the schema vocabulary
    rather than echoing the surface form of the question.
    """
    slots = {}
    q_lower = question.lower()

    # Helper function for vocabulary matching
    def find_canonical(text, vocab):
        for item in vocab:
            if item.lower() in text.lower():
                return item
        return None

    # 1. & 2. Handle specific extraction logic based on shape
    
    # Extract Cuisine (Needed for Q3, Q4, Q5, Q6, Q9, Q11, Q12 + Tier 1: Q17, Q18, Q19)
    if shape in [ShapeId.Q3, ShapeId.Q4, ShapeId.Q5, ShapeId.Q6, ShapeId.Q9, ShapeId.Q11, ShapeId.Q12, ShapeId.Q17, ShapeId.Q18, ShapeId.Q19]:
        slots["cuisine"] = find_canonical(question, CUISINES)

    # Extract Ingredient (Needed for Q1, Q5, Q6, Q8, Q13, Q14 + Tier 1: Q19)
    if shape in [ShapeId.Q1, ShapeId.Q5, ShapeId.Q6, ShapeId.Q8, ShapeId.Q13, ShapeId.Q19]:
        slots["ingredient"] = find_canonical(question, INGREDIENTS)

    # Extract Author (Needed for Q2, Q8 + Tier 1: Q16, Q18, Q19, Q20)
    if shape in [ShapeId.Q2, ShapeId.Q8, ShapeId.Q16, ShapeId.Q18, ShapeId.Q19, ShapeId.Q20] and nlp:
        doc = nlp(question)
        authors = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
        if authors:
            slots["author"] = authors[0]
        else:
            # Fallback if NER misses but "by [Name]" is present
            match = re.search(r"by (?:author )?([A-Z][a-z]+ [A-Z][a-z]+)", question)
            if match:
                slots["author"] = match.group(1)

    # Extract Technique (Needed for Q7, Q15 + Tier 1: Q16, Q17)
    if shape in [ShapeId.Q7, ShapeId.Q15, ShapeId.Q16, ShapeId.Q17]:
        slots["technique"] = find_canonical(question, TECHNIQUES)

    # Special Case Q10: Numeric threshold
    if shape == ShapeId.Q10:
        match = re.search(r"under (\d+)", q_lower)
        if match:
            slots["max_minutes"] = int(match.group(1))

    # Special Case Q14: Negation
    if shape == ShapeId.Q14:
        # Split to separate positive and negative ingredients
        parts = re.split(r"but not|without", q_lower)
        slots["ingredient"] = find_canonical(parts[0], INGREDIENTS)
        if len(parts) > 1:
            slots["exclude_ingredient"] = find_canonical(parts[1], INGREDIENTS)

    # 3. Return the dict.
    return slots