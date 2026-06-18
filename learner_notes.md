# Integration 9B — Learner Notes

Document your design choices and what you learned. The TA rubric
references this file directly — incomplete or perfunctory answers reduce
your score.

## 1. Intents you handled and how you classified them

Describe your `detect_shape` rules. Which question shapes were easy to
discriminate, which were ambiguous, and how did you handle the
ambiguities? Cite at least one specific question from
`data/eval_questions.jsonl` where two shapes were plausible candidates.

In my implementation of `detect_shape`, I used a rule-based approach with a strict priority order. Shapes like Q3 ("Find Italian recipes") and Q1 ("Find recipes that use ginger") were easy to discriminate because they relied on single keywords and direct mappings. However, complex shapes like Q14 (negation) and Q8 (multi-entity conjunction) presented ambiguity. 

For example, the question **"Find recipes that use ginger but not garlic"** could plausibly be classified as **Q1** (simple ingredient use) or **Q14** (negation). To handle this, I implemented a "Specific-to-General" priority queue. By checking for the presence of negation keywords ("but not", "without") before checking for simple ingredient patterns, I ensured that Q14 was selected correctly. This prevents the "silent failure" mode where a sub-string match triggers a simpler, incorrect intent.

## 2. A question that worked end-to-end

Pick one of the 15 canonical questions, walk through the pipeline:
what `detect_shape` returned, what `extract_slots` returned, the
compiled Cypher (with $param placeholders), the bound params dict, and
the rows the driver returned. Paste the actual CLI output.

I chose the question: **"Find Sichuan recipes that use ginger"**

*   **detect_shape**: Returned `ShapeId.Q5` (Conjunction of Cuisine and Ingredient).
*   **extract_slots**: Returned `{"cuisine": "Sichuan", "ingredient": "ginger"}`.
*   **Compiled Cypher**: 
    `MATCH (r:Recipe)-[:OF_CUISINE]->(:Cuisine {name: $cuisine}), (r)-[:USES_INGREDIENT]->(:Ingredient {name: $ingredient}) RETURN r.name AS recipe ORDER BY r.name`
*   **Params Dict**: `{"cuisine": "Sichuan", "ingredient": "ginger"}`.
*   **CLI Output**:
```text
{'recipe': 'Dan Dan Noodles'}
{'recipe': 'Fish Fragrant Eggplant'}
{'recipe': 'Kung Pao Chicken'}
{'recipe': 'Mapo Tofu'}
{'recipe': 'Mapo Tofu #2'}
{'recipe': 'Sichuan Hotpot'}
```

## 3. A failure mode you diagnosed

Either a question that you initially mis-classified (and why), or an
adversarial / off-template question and what your `UnsupportedQueryError`
message told the caller. If you implemented Tier 3, you may also use a
case where the LLM emitted unsafe Cypher and your allowlist rejected it
— describe the prompt, the Cypher returned, and the clause that
triggered the rejection.

I tested the adversarial question: **"Find tomato (which is a fruit)"**. 
Initially, a naive keyword scan might have classified this as **Q1** simply because "tomato" is an ingredient. However, the system correctly diagnosed this as a failure because the question lacks the required context cues like "use" or "with". 

My `detect_shape` returned `None`, which triggered an `UnsupportedQueryError`. The error message explicitly listed all 15 supported templates, effectively telling the user that the system expects a specific structure (e.g., "Find recipes that use tomato") rather than just a mention of the entity. This "fail-loud" approach is crucial for debugging and managing user expectations in a schema-bounded system.

## 4. A design tradeoff between the deterministic mapper and the Tier 3 chain

When would you prefer the deterministic mapper over the LLM chain in
production, and vice versa? Cite a concrete dimension (latency,
auditability, schema-coverage cost, distribution-shift robustness,
operational risk) for each side. Both implementations are first-class —
your answer should reflect that, not pick a winner.

The choice between a deterministic mapper and a Tier 3 LLM chain depends on the production requirements:

*   **Deterministic Mapper (Preferred for Auditability and Latency):** In a production environment where every answer must be explainable (e.g., a medical or financial recipe app), the deterministic mapper is superior because the Cypher is generated from a "white-box" template. We know exactly why a result was returned. Additionally, it has near-zero latency compared to the seconds-long inference time of an LLM.
*   **Tier 3 LLM Chain (Preferred for Distribution-Shift Robustness):** If the input distribution is "open" and users ask questions in highly varied, conversational ways (e.g., "I'm looking for something spicy from China but I hate garlic"), the LLM chain is much more robust. Scaling a deterministic mapper to cover every possible linguistic variation (schema-coverage cost) becomes prohibitively expensive, whereas an LLM handles these shifts naturally by understanding the semantics of the request.
