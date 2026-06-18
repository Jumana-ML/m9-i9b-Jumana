"""End-to-end NL-question pipeline against the recipe KG.

Wires `mapper.detect_shape → mapper.extract_slots → mapper.compile_to_cypher
→ driver.session().run(cypher, **params)` into one function. Raises
`UnsupportedQueryError` (fail-loud) when the question is off-template.
"""

from mapper import (
    detect_shape,
    extract_slots,
    compile_to_cypher,
    UnsupportedQueryError,
)


def answer(driver, question: str) -> list[dict]:
    """Answer one NL question by routing through the deterministic mapper.

    Returns a list of result rows (each row a dict whose keys are the
    Cypher RETURN aliases). Raises UnsupportedQueryError when
    detect_shape returns None — surface that to the caller; do not
    swallow it into an empty result list.
    """
    # 1. Call detect_shape(question). If it returns None, raise
    #    UnsupportedQueryError(question) — fail-loud is part of the
    #    contract, do NOT return [].
    shape = detect_shape(question)
    if shape is None:
        raise UnsupportedQueryError(question)

    # 2. Call extract_slots(question, shape) to fill the slot dict.
    slots = extract_slots(question, shape)

    # 3. Call compile_to_cypher(shape, slots) to get (cypher, params).
    cypher, params = compile_to_cypher(shape, slots)

    # 4. Open a session on `driver`, run `session.run(cypher, **params)`,
    #    and convert each row to a plain dict via row.data().
    with driver.session() as session:
        result = session.run(cypher, **params)
        
        # 5. Return the list of dicts.
        return [row.data() for row in result]