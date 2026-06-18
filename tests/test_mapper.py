"""Core deterministic-mapper autograder — LLM-FREE.

Runs entirely against the Neo4j fixture loaded by load_fixture.py. No
LLM calls, no network calls beyond Bolt.
"""

from __future__ import annotations

import ast
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mapper import (  # noqa: E402
    CANONICAL_CYPHER,
    ShapeId,
    UnsupportedQueryError,
)
from mapper import compile as compile_mod  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
EVAL_PATH = DATA_DIR / "eval_questions.jsonl"


# ---------------------------------------------------------------------------
# learner_notes.md must be touched (rubric-graded deliverable)
# ---------------------------------------------------------------------------

# MD5 of the unmodified starter learner_notes.md template. If the student's
# file still hashes to this value, they have not filled it in.
_UNMODIFIED_LEARNER_NOTES_MD5 = "a7ff35ce0a0f977dbe1e2d19d5906b56"


def test_learner_notes_modified():
    """Sentinel: `learner_notes.md` is a TA-rubric-graded deliverable. The
    autograder cannot judge content quality, but it can reject the
    unmodified template. A submission whose `learner_notes.md` is
    byte-identical to the starter has not been filled in and must fail
    CI — the rubric expects narrative answers in place of the
    `> _Your answer here._` placeholders.
    """
    import hashlib
    notes = REPO_ROOT / "learner_notes.md"
    assert notes.exists(), "learner_notes.md is missing from the submission"
    h = hashlib.md5(notes.read_bytes()).hexdigest()
    assert h != _UNMODIFIED_LEARNER_NOTES_MD5, (
        "learner_notes.md is the unmodified starter template. Fill in the "
        "narrative answers (each `> _Your answer here._` placeholder is a "
        "prompt) before resubmitting."
    )
    # Also flag the textual placeholder explicitly — covers the case
    # where a learner edits a header or adds a single character but
    # leaves the prompts unanswered.
    text = notes.read_text()
    placeholder_count = text.count("_Your answer here._")
    assert placeholder_count == 0, (
        f"learner_notes.md still contains {placeholder_count} unanswered "
        "`_Your answer here._` placeholder(s). Replace each one with a "
        "narrative answer."
    )


def _load_eval() -> list[dict]:
    return [json.loads(line) for line in EVAL_PATH.read_text().splitlines() if line.strip()]


EVAL = _load_eval()
assert len(EVAL) == 20, f"eval_questions.jsonl must have 15 entries, has {len(EVAL)}"


ADVERSARIAL_QUESTIONS = [
    "what is the meaning of life",
    "delete all recipes",
    "write me a poem",
    "find tomato (which is a fruit)",
]


# --------------------------------------------------------------------------- fixture acceptance

def test_load_fixture_acceptance(driver):
    """The fixture was loaded with the expected counts (load_fixture.py
    runs before pytest in CI; this is a sanity re-check inside the
    pytest session).
    """
    with driver.session() as s:
        total = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        rels = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
    # ±2% tolerance — same as load_fixture.py.
    assert abs(total - 200) / 200 <= 0.02, f"expected ~200 nodes, got {total}"
    assert abs(rels - 803) / 803 <= 0.02, f"expected ~803 rels, got {rels}"


def test_entity_id_uniqueness(driver):
    """Identity Discipline holds: no duplicate :Entity.id rows."""
    with driver.session() as s:
        rows = list(s.run(
            "MATCH (n:Entity) "
            "WITH n.id AS id, count(*) AS c "
            "WHERE c > 1 RETURN id, c"
        ))
    assert rows == [], f"Duplicate :Entity.id rows: {rows}"


# --------------------------------------------------------------------------- intent classifier

def test_detect_shape_for_each_of_15_questions():
    """detect_shape classifies each canonical question to the gold shape."""
    from mapper import detect_shape  # imported here so unmodified-starter test isolates

    for entry in EVAL:
        got = detect_shape(entry["question_text"])
        assert got is not None, f"detect_shape returned None for {entry['question_text']!r}"
        assert got.value == entry["shape"], (
            f"detect_shape({entry['question_text']!r}) -> {got.value}, "
            f"expected {entry['shape']}"
        )


def test_detect_shape_unknown_for_4_adversarial():
    """Off-template questions return None — never a confident wrong shape."""
    from mapper import detect_shape

    for q in ADVERSARIAL_QUESTIONS:
        got = detect_shape(q)
        assert got is None, f"detect_shape({q!r}) returned {got}; expected None"


# --------------------------------------------------------------------------- slot extraction

def test_extract_slots_returns_correct_slots():
    """extract_slots returns the gold slot dict for each canonical question."""
    from mapper import extract_slots

    for entry in EVAL:
        shape = ShapeId(entry["shape"])
        got = extract_slots(entry["question_text"], shape)
        assert got == entry["slots"], (
            f"extract_slots({entry['question_text']!r}, {shape}) -> {got}, "
            f"expected {entry['slots']}"
        )


# --------------------------------------------------------------------------- compile

def test_compile_to_cypher_returns_parameterized():
    """For each shape, the returned cypher contains $<name> for every slot."""
    from mapper import compile_to_cypher

    for entry in EVAL:
        shape = ShapeId(entry["shape"])
        slots = entry["slots"]
        cypher, params = compile_to_cypher(shape, slots)
        assert isinstance(cypher, str) and cypher.strip(), "cypher must be a non-empty string"
        for slot_name in slots:
            assert f"${slot_name}" in cypher, (
                f"shape {shape.value} cypher missing $<{slot_name}> parameter token; "
                f"cypher was: {cypher!r}"
            )
        # The returned cypher MUST be the canonical template (no string formatting).
        assert cypher == CANONICAL_CYPHER[shape], (
            f"compile_to_cypher must return the canonical template unchanged; "
            f"shape={shape.value}"
        )
        assert params == slots, "params dict must equal the input slots"


def test_compile_to_cypher_no_fstring_interpolation():
    """AST inspection: compile.py must not f-string slot values into Cypher.

    Walks every JoinedStr (f-string) node in compile.py source. A FormattedValue
    inside an f-string whose source contains the text 'slots' or 'slot'
    is the silent-failure pattern the Reading warns against.
    """
    src = Path(compile_mod.__file__).read_text()
    tree = ast.parse(src)
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            for piece in node.values:
                if isinstance(piece, ast.FormattedValue):
                    expr_src = ast.unparse(piece.value)
                    if "slot" in expr_src.lower():
                        offenders.append(expr_src)
    assert not offenders, (
        f"compile.py contains f-string interpolation of slot values "
        f"(silent SQL/Cypher-injection class): {offenders}. Use the "
        f"$param template-from-dict pattern instead."
    )


# --------------------------------------------------------------------------- end-to-end pipeline

def _canonical_rows(driver, shape: ShapeId, slots: dict) -> list[dict]:
    cypher = CANONICAL_CYPHER[shape]
    with driver.session() as s:
        return [row.data() for row in s.run(cypher, **slots)]


def _normalize_rows(rows, shape: ShapeId):
    """For non-ranked shapes (everything but q9/q12) compare as sets;
    for q9 and q12 compare order.
    """
    if shape in (ShapeId.Q9, ShapeId.Q12):
        return rows
    return sorted([tuple(sorted(r.items())) for r in rows])


def test_pipeline_runs_each_question(driver):
    """Full pipeline against Neo4j on all 15 canonical questions; rows
    must match the canonical Cypher's rows.
    """
    from pipeline import answer

    for entry in EVAL:
        shape = ShapeId(entry["shape"])
        gold = _canonical_rows(driver, shape, entry["slots"])
        got = answer(driver, entry["question_text"])
        assert _normalize_rows(got, shape) == _normalize_rows(gold, shape), (
            f"pipeline answer for {entry['question_text']!r} (shape={shape.value}) "
            f"did not match canonical result set.\ngot={got}\ngold={gold}"
        )


def test_pipeline_raises_unsupported_for_off_template(driver):
    """Adversarial questions raise UnsupportedQueryError; message names
    every supported shape.
    """
    from pipeline import answer

    for q in ADVERSARIAL_QUESTIONS:
        with pytest.raises(UnsupportedQueryError) as exc:
            answer(driver, q)
        msg = str(exc.value)
        # All 15 shape names must appear in the fail-loud message.
        for shape in ShapeId:
            assert shape.value in msg, (
                f"UnsupportedQueryError message must name every supported "
                f"shape; missing {shape.value}. message={msg!r}"
            )


def test_pipeline_subclass_traversal_question_q4(driver):
    """Q4 'Find Asian recipes' returns every recipe whose cuisine is in
    the Asian subtree — load-bearing hierarchy reasoning.
    """
    from pipeline import answer

    rows = answer(driver, "Find Asian recipes")
    names = {r["recipe"] for r in rows}
    # The fixture seeds Sichuan, Japanese, Indian, Thai, Chinese under
    # Asian. Every Sichuan recipe must be in the answer.
    with driver.session() as s:
        sichuan_recipes = {
            r["name"] for r in s.run(
                "MATCH (r:Recipe)-[:OF_CUISINE]->(:Cuisine {name: 'Sichuan'}) RETURN r.name AS name"
            )
        }
        japanese_recipes = {
            r["name"] for r in s.run(
                "MATCH (r:Recipe)-[:OF_CUISINE]->(:Cuisine {name: 'Japanese'}) RETURN r.name AS name"
            )
        }
    # Subclass traversal must include both — pipeline that only matches
    # direct OF_CUISINE on 'Asian' would miss these.
    assert sichuan_recipes.issubset(names), (
        f"Q4 missed Sichuan descendants of Asian. missing={sichuan_recipes - names}"
    )
    assert japanese_recipes.issubset(names), (
        f"Q4 missed Japanese descendants of Asian. missing={japanese_recipes - names}"
    )


def test_pipeline_conjunction_question_q5(driver):
    """Q5 'Find Sichuan recipes that use ginger' is the AND-intersection."""
    from pipeline import answer

    rows = answer(driver, "Find Sichuan recipes that use ginger")
    names = {r["recipe"] for r in rows}
    with driver.session() as s:
        gold = {
            r["name"] for r in s.run(
                "MATCH (r:Recipe)-[:OF_CUISINE]->(:Cuisine {name: 'Sichuan'}) "
                "MATCH (r)-[:USES_INGREDIENT]->(:Ingredient {name: 'ginger'}) "
                "RETURN r.name AS name"
            )
        }
    assert names == gold, f"Q5 intersection mismatch. expected={gold}, got={names}"


def test_pipeline_negation_question_q14(driver):
    """Q14 'Find recipes that use ginger but not garlic' is NOT-EXISTS."""
    from pipeline import answer

    rows = answer(driver, "Find recipes that use ginger but not garlic")
    names = {r["recipe"] for r in rows}
    with driver.session() as s:
        gold = {
            r["name"] for r in s.run(
                "MATCH (r:Recipe)-[:USES_INGREDIENT]->(:Ingredient {name: 'ginger'}) "
                "WHERE NOT EXISTS { "
                "  MATCH (r)-[:USES_INGREDIENT]->(:Ingredient {name: 'garlic'}) "
                "} RETURN r.name AS name"
            )
        }
    assert names == gold, f"Q14 negation mismatch. expected={gold}, got={names}"


# --------------------------------------------------------------------------- CLI

def test_cli_runs():
    """`python cli.py "Find Italian recipes"` exits 0 with non-empty stdout."""
    proc = subprocess.run(
        [sys.executable, "cli.py", "Find Italian recipes"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
        env={
            **os.environ,
            "NEO4J_URI": os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            "NEO4J_USER": os.environ.get("NEO4J_USER", "neo4j"),
            "NEO4J_PASSWORD": os.environ.get("NEO4J_PASSWORD", "testtest"),
        },
    )
    assert proc.returncode == 0, (
        f"cli.py exited {proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}"
    )
    assert proc.stdout.strip(), f"cli.py produced empty stdout. stderr={proc.stderr}"


# --------------------------------------------------------------------------- sentinel

def test_starter_unmodified_fails():
    """Sentinel: an unmodified starter must surface NotImplementedError
    from the TODO functions. This is the silent-pass guard.
    """
    from mapper import intent as intent_mod, slots as slots_mod, compile as compile_mod2

    src_files = [
        Path(intent_mod.__file__).read_text(),
        Path(slots_mod.__file__).read_text(),
        Path(compile_mod2.__file__).read_text(),
    ]
    # If every TODO function still raises NotImplementedError, this test
    # is meant to FAIL — the autograder uses it to verify that the
    # unmodified-starter pytest run produces ≥1 failure.
    unimpl = sum(s.count('raise NotImplementedError') for s in src_files)
    assert unimpl == 0, (
        f"Sentinel: {unimpl} NotImplementedError sites remain in "
        f"mapper/intent.py + mapper/slots.py + mapper/compile.py — "
        f"implement the TODO functions before submitting."
    )
