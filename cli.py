"""Command-line entry point: python cli.py "Find Italian recipes"

Connects to Neo4j (env vars or local docker-compose defaults), routes the
question through the pipeline, and pretty-prints the top results. Exit 0
on success, 1 if the pipeline raises UnsupportedQueryError, 2 on any
other error.
"""

from __future__ import annotations

import os
import sys

from neo4j import GraphDatabase

from mapper import UnsupportedQueryError
from pipeline import answer


NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "testtest")


def main(argv: list[str]) -> int:
    """Parse argv, route the question, pretty-print rows.

    Required behaviour:
      - Read the question from argv[1]; print a usage hint and exit 2
        if missing.
      - Open a Neo4j driver, route through pipeline.answer.
      - Print each row on its own line; if rows is empty, print
        "(no results)".
      - Catch UnsupportedQueryError and print its message to stderr
        with exit code 1.
    """
    # 1. Parse argv to extract the question text. Print usage if missing.
    if len(argv) < 2:
        print("Usage: python cli.py \"Your NL question here\"", file=sys.stderr)
        return 2
    
    question = argv[1]

    # 2. Build a Neo4j driver from the env vars above.
    # Note: On some Windows setups, you might need to use 127.0.0.1 instead of localhost
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        # 3. Call answer(driver, question); pretty-print the rows.
        rows = answer(driver, question)
        
        if not rows:
            print("(no results)")
        else:
            for row in rows:
                print(row)
        
        return 0

    except UnsupportedQueryError as e:
        # 4. Handle UnsupportedQueryError → stderr message + exit 1.
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    except Exception as e:
        # Handle any other unexpected errors
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 2

    finally:
        # 5. Close the driver in a finally block.
        driver.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv))