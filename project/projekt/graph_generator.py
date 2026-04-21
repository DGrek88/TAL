from __future__ import annotations

import random
from dataclasses import dataclass

from io_utils import Edge, ProblemInstance, WeightedGraph, normalize_edge


@dataclass(frozen=True)
class GeneratorConfig:
    n: int
    m: int
    k: int
    source: int
    target: int
    min_weight: int = 1
    max_weight: int = 20
    seed: int | None = None
    disjointness: str = "vertex"


PRESET_CLASSES: dict[str, GeneratorConfig] = {
    "small": GeneratorConfig(n=12, m=22, k=3, source=0, target=11, min_weight=1, max_weight=15, seed=101),
    "medium": GeneratorConfig(n=20, m=42, k=3, source=0, target=19, min_weight=1, max_weight=20, seed=202),
    "large": GeneratorConfig(n=32, m=80, k=4, source=0, target=31, min_weight=1, max_weight=25, seed=303),
}


def minimum_edge_count_for_generator(n: int, k: int) -> int:
    """Lower bound required by the constructive generator used in this project."""
    return n + k - 2


def generate_instance(config: GeneratorConfig) -> ProblemInstance:
    if config.n < 4:
        raise ValueError("At least 4 vertices are required.")
    if config.k <= 2:
        raise ValueError("The assignment assumes k > 2.")
    if config.source == config.target:
        raise ValueError("Source and target must be different.")
    if not (0 <= config.source < config.n and 0 <= config.target < config.n):
        raise ValueError("Source and target must be valid vertices.")
    if config.min_weight <= 0 or config.max_weight < config.min_weight:
        raise ValueError("Weights must be positive and satisfy min_weight <= max_weight.")
    if config.disjointness not in {"vertex", "edge"}:
        raise ValueError("Disjointness must be either 'vertex' or 'edge'.")

    if config.n < config.k + 1:
        raise ValueError(
            "For this generator, vertex-disjoint construction requires n >= k + 1 "
            "(one direct path s-t and k-1 paths through distinct internal vertices)."
        )

    minimum_edges = minimum_edge_count_for_generator(config.n, config.k)
    if config.m < minimum_edges:
        raise ValueError(
            f"For this generator m must be at least {minimum_edges} "
            f"to guarantee connectivity and k disjoint candidate paths."
        )

    max_edges = config.n * (config.n - 1) // 2
    if config.m > max_edges:
        raise ValueError(f"Simple undirected graph on {config.n} vertices can have at most {max_edges} edges.")

    rng = random.Random(config.seed)
    vertices = list(range(config.n))
    internal_pool = [vertex for vertex in vertices if vertex not in {config.source, config.target}]
    rng.shuffle(internal_pool)

    path_intermediates = internal_pool[: config.k - 1]
    backbone_vertices = {config.source, config.target, *path_intermediates}

    used_edges: set[tuple[int, int]] = set()
    edges: list[Edge] = []

    def add_edge(u: int, v: int) -> None:
        key = normalize_edge(u, v)
        if u == v or key in used_edges:
            return
        used_edges.add(key)
        weight = rng.randint(config.min_weight, config.max_weight)
        edges.append(Edge(u=u, v=v, weight=float(weight)))

    # Path 1 is the direct edge s-t, and the remaining k-1 paths use distinct internal vertices.
    add_edge(config.source, config.target)
    for middle in path_intermediates:
        add_edge(config.source, middle)
        add_edge(middle, config.target)

    # Connect every remaining vertex to the existing backbone to ensure graph connectivity.
    connected_vertices = set(backbone_vertices)
    remaining_vertices = [vertex for vertex in vertices if vertex not in connected_vertices]
    for vertex in remaining_vertices:
        anchor = rng.choice(sorted(connected_vertices))
        add_edge(vertex, anchor)
        connected_vertices.add(vertex)

    possible_extra_edges = [
        (u, v)
        for u in range(config.n)
        for v in range(u + 1, config.n)
        if normalize_edge(u, v) not in used_edges
    ]
    rng.shuffle(possible_extra_edges)

    while len(edges) < config.m and possible_extra_edges:
        u, v = possible_extra_edges.pop()
        add_edge(u, v)

    if len(edges) != config.m:
        raise RuntimeError("Could not generate the requested number of edges.")

    graph = WeightedGraph(n=config.n, edges=edges)
    return ProblemInstance(
        graph=graph,
        k=config.k,
        source=config.source,
        target=config.target,
        disjointness=config.disjointness,
        name=f"generated(n={config.n},m={config.m},k={config.k},seed={config.seed})",
    )


def preset_config(name: str, seed: int | None = None, disjointness: str = "vertex") -> GeneratorConfig:
    if name not in PRESET_CLASSES:
        available = ", ".join(sorted(PRESET_CLASSES))
        raise ValueError(f"Unknown preset '{name}'. Available presets: {available}")

    base = PRESET_CLASSES[name]
    return GeneratorConfig(
        n=base.n,
        m=base.m,
        k=base.k,
        source=base.source,
        target=base.target,
        min_weight=base.min_weight,
        max_weight=base.max_weight,
        seed=base.seed if seed is None else seed,
        disjointness=disjointness,
    )
