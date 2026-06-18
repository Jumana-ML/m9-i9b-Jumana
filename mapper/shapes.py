"""Canonical question shapes + gold Cypher templates (course-provided).

These 15 templates ARE the autograder gold for both the deterministic
mapper and the Tier 3 chain. Do not modify — your `compile_to_cypher`
implementation selects from this dict; your `intent.detect_shape`
classifier returns one of these ShapeId values.

Every template is parameterized with `$param` syntax — never f-string
interpolation of slot values into the query.

Subclass-traversal templates (q4, q6, q12, q13) use `[:SUBCLASS_OF*0..]`
so the answer set includes the named taxon AND all descendants.
"""

from enum import Enum


class ShapeId(str, Enum):
    Q1 = "q1"    # USES_INGREDIENT
    Q2 = "q2"    # BY_AUTHOR
    Q3 = "q3"    # OF_CUISINE direct
    Q4 = "q4"    # OF_CUISINE + SUBCLASS_OF traversal
    Q5 = "q5"    # OF_CUISINE direct + USES_INGREDIENT
    Q6 = "q6"    # OF_CUISINE traversal + USES_INGREDIENT
    Q7 = "q7"    # REQUIRES_TECHNIQUE
    Q8 = "q8"    # BY_AUTHOR + USES_INGREDIENT
    Q9 = "q9"    # OF_CUISINE direct ORDER BY popularity
    Q10 = "q10"  # prepMinutes property filter
    Q11 = "q11"  # inverse — ingredients OF cuisine recipes
    Q12 = "q12"  # authors of cuisine subtree, ranked
    Q13 = "q13"  # ingredient hierarchy
    Q14 = "q14"  # negation via NOT EXISTS
    Q15 = "q15"  # OPTIONAL MATCH on technique
    # Tier 1 Challenge Extensions (16-20)
    Q16 = "q16"  # Author + Technique
    Q17 = "q17"  # Cuisine + Technique
    Q18 = "q18"  # Cuisine + Author
    Q19 = "q19"  # Cuisine + Author + Ingredient (Multi-hop conjunction)
    Q20 = "q20"  # Inverse: Ingredients used by specific Author


# Canonical Cypher per shape. All RETURN columns include "recipe" as the
# primary key (recipe name) so result-set equivalence comparisons in the
# autograder can compare on a stable projection. Limits are present so
# CI run-time and assertion size stay bounded.
CANONICAL_CYPHER: dict[ShapeId, str] = {
    ShapeId.Q1: (
        "MATCH (r:Recipe)-[:USES_INGREDIENT]->(:Ingredient {name: $ingredient}) "
        "RETURN r.name AS recipe "
        "ORDER BY r.name "
        "LIMIT 50"
    ),
    ShapeId.Q2: (
        "MATCH (r:Recipe)-[:BY_AUTHOR]->(:Author {name: $author}) "
        "RETURN r.name AS recipe "
        "ORDER BY r.name "
        "LIMIT 50"
    ),
    ShapeId.Q3: (
        "MATCH (r:Recipe)-[:OF_CUISINE]->(:Cuisine {name: $cuisine}) "
        "RETURN r.name AS recipe "
        "ORDER BY r.name "
        "LIMIT 50"
    ),
    ShapeId.Q4: (
        "MATCH (r:Recipe)-[:OF_CUISINE]->(c:Cuisine) "
        "MATCH (c)-[:SUBCLASS_OF*0..]->(:Cuisine {name: $cuisine}) "
        "RETURN r.name AS recipe "
        "ORDER BY r.name "
        "LIMIT 50"
    ),
    ShapeId.Q5: (
        "MATCH (r:Recipe)-[:OF_CUISINE]->(:Cuisine {name: $cuisine}) "
        "MATCH (r)-[:USES_INGREDIENT]->(:Ingredient {name: $ingredient}) "
        "RETURN r.name AS recipe "
        "ORDER BY r.name "
        "LIMIT 50"
    ),
    ShapeId.Q6: (
        "MATCH (r:Recipe)-[:OF_CUISINE]->(c:Cuisine) "
        "MATCH (c)-[:SUBCLASS_OF*0..]->(:Cuisine {name: $cuisine}) "
        "MATCH (r)-[:USES_INGREDIENT]->(:Ingredient {name: $ingredient}) "
        "RETURN r.name AS recipe "
        "ORDER BY r.name "
        "LIMIT 50"
    ),
    ShapeId.Q7: (
        "MATCH (r:Recipe)-[:REQUIRES_TECHNIQUE]->(:Technique {name: $technique}) "
        "RETURN r.name AS recipe "
        "ORDER BY r.name "
        "LIMIT 50"
    ),
    ShapeId.Q8: (
        "MATCH (r:Recipe)-[:BY_AUTHOR]->(:Author {name: $author}) "
        "MATCH (r)-[:USES_INGREDIENT]->(:Ingredient {name: $ingredient}) "
        "RETURN r.name AS recipe "
        "ORDER BY r.name "
        "LIMIT 50"
    ),
    ShapeId.Q9: (
        "MATCH (r:Recipe)-[:OF_CUISINE]->(:Cuisine {name: $cuisine}) "
        "RETURN r.name AS recipe, r.popularityScore AS popularity "
        "ORDER BY r.popularityScore DESC, r.name ASC "
        "LIMIT 10"
    ),
    ShapeId.Q10: (
        "MATCH (r:Recipe) "
        "WHERE r.prepMinutes < $max_minutes "
        "RETURN r.name AS recipe, r.prepMinutes AS prepMinutes "
        "ORDER BY r.name "
        "LIMIT 50"
    ),
    ShapeId.Q11: (
        "MATCH (r:Recipe)-[:OF_CUISINE]->(:Cuisine {name: $cuisine}) "
        "MATCH (r)-[:USES_INGREDIENT]->(i:Ingredient) "
        "RETURN DISTINCT i.name AS ingredient "
        "ORDER BY i.name "
        "LIMIT 50"
    ),
    ShapeId.Q12: (
        "MATCH (r:Recipe)-[:OF_CUISINE]->(c:Cuisine) "
        "MATCH (c)-[:SUBCLASS_OF*0..]->(:Cuisine {name: $cuisine}) "
        "MATCH (r)-[:BY_AUTHOR]->(a:Author) "
        "RETURN DISTINCT a.name AS author, count(r) AS recipe_count "
        "ORDER BY recipe_count DESC, a.name ASC "
        "LIMIT 10"
    ),
    ShapeId.Q13: (
        "MATCH (i:Ingredient {name: $ingredient}) "
        "MATCH (descendant:Ingredient)-[:SUBCLASS_OF*0..]->(i) "
        "MATCH (r:Recipe)-[:USES_INGREDIENT]->(descendant) "
        "RETURN DISTINCT r.name AS recipe "
        "ORDER BY r.name "
        "LIMIT 50"
    ),
    ShapeId.Q14: (
        "MATCH (r:Recipe)-[:USES_INGREDIENT]->(:Ingredient {name: $ingredient}) "
        "WHERE NOT EXISTS { "
        "  MATCH (r)-[:USES_INGREDIENT]->(:Ingredient {name: $exclude_ingredient}) "
        "} "
        "RETURN r.name AS recipe "
        "ORDER BY r.name "
        "LIMIT 50"
    ),
    ShapeId.Q15: (
        "MATCH (r:Recipe) "
        "OPTIONAL MATCH (r)-[:REQUIRES_TECHNIQUE]->(t:Technique {name: $technique}) "
        "RETURN r.name AS recipe, t.name AS technique "
        "ORDER BY r.name "
        "LIMIT 50"
    ),
    # Challenge Tier 1 Templates
    ShapeId.Q16: (
        "MATCH (r:Recipe)-[:BY_AUTHOR]->(:Author {name: $author}) "
        "MATCH (r)-[:REQUIRES_TECHNIQUE]->(:Technique {name: $technique}) "
        "RETURN r.name AS recipe "
        "ORDER BY r.name "
        "LIMIT 50"
    ),
    ShapeId.Q17: (
        "MATCH (r:Recipe)-[:OF_CUISINE]->(:Cuisine {name: $cuisine}) "
        "MATCH (r)-[:REQUIRES_TECHNIQUE]->(:Technique {name: $technique}) "
        "RETURN r.name AS recipe "
        "ORDER BY r.name "
        "LIMIT 50"
    ),
    ShapeId.Q18: (
        "MATCH (r:Recipe)-[:OF_CUISINE]->(:Cuisine {name: $cuisine}) "
        "MATCH (r)-[:BY_AUTHOR]->(:Author {name: $author}) "
        "RETURN r.name AS recipe "
        "ORDER BY r.name "
        "LIMIT 50"
    ),
    ShapeId.Q19: (
        "MATCH (r:Recipe)-[:OF_CUISINE]->(:Cuisine {name: $cuisine}) "
        "MATCH (r)-[:BY_AUTHOR]->(:Author {name: $author}) "
        "MATCH (r)-[:USES_INGREDIENT]->(:Ingredient {name: $ingredient}) "
        "RETURN r.name AS recipe "
        "ORDER BY r.name "
        "LIMIT 50"
    ),
    ShapeId.Q20: (
        "MATCH (a:Author {name: $author})<-[:BY_AUTHOR]-(r:Recipe)-[:USES_INGREDIENT]->(i:Ingredient) "
        "RETURN DISTINCT i.name AS ingredient "
        "ORDER BY i.name "
        "LIMIT 50"
    ),
}