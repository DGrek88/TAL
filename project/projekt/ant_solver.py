from __future__ import annotations

import random
from dataclasses import dataclass

from greedy_solver import shortest_distances_from_target
from io_utils import ProblemInstance, SolverResult, normalize_edge, validate_paths


@dataclass(frozen=True)
class AntColonyConfig:
    ants: int = 24
    iterations: int = 45
    alpha: float = 1.0
    beta: float = 3.0
    evaporation: float = 0.25
    deposit_factor: float = 45.0
    exploitation_probability: float = 0.15
    max_path_attempts: int = 10
    seed: int | None = None


@dataclass
class AntCandidate:
    paths: list[list[int]]
    total_cost: float

    @property
    def complete(self) -> bool:
        return False


@dataclass
class ConcreteAntCandidate(AntCandidate):
    k: int = 0

    @property
    def complete(self) -> bool:
        return len(self.paths) == self.k


def solve_ant_colony(instance: ProblemInstance, config: AntColonyConfig | None = None) -> SolverResult:
    solver_config = config or AntColonyConfig()
    rng = random.Random(solver_config.seed)
    pheromones = {normalize_edge(edge.u, edge.v): 1.0 for edge in instance.graph.edges}
    target_distances = shortest_distances_from_target(instance)

    best = ConcreteAntCandidate(paths=[], total_cost=float("inf"), k=instance.k)

    for _ in range(solver_config.iterations):
        iteration_candidates = [
            _build_candidate(
                instance=instance,
                pheromones=pheromones,
                target_distances=target_distances,
                rng=rng,
                config=solver_config,
            )
            for _ in range(solver_config.ants)
        ]

        for candidate in iteration_candidates:
            if _is_better(candidate, best):
                best = candidate

        _evaporate(pheromones, solver_config.evaporation)

        complete_candidates = [candidate for candidate in iteration_candidates if candidate.complete]
        if complete_candidates:
            complete_candidates.sort(key=lambda candidate: candidate.total_cost)
            deposit_candidates = complete_candidates[: min(3, len(complete_candidates))]
        else:
            iteration_candidates.sort(key=lambda candidate: (-len(candidate.paths), candidate.total_cost))
            deposit_candidates = iteration_candidates[:1]

        for candidate in deposit_candidates:
            _deposit_pheromones(
                pheromones=pheromones,
                candidate=candidate,
                instance=instance,
                factor=solver_config.deposit_factor,
            )

        if best.complete:
            _deposit_pheromones(
                pheromones=pheromones,
                candidate=best,
                instance=instance,
                factor=solver_config.deposit_factor * 0.35,
            )

    path_costs = [instance.graph.path_cost(path) for path in best.paths]
    valid, message = validate_paths(instance, best.paths)
    if not valid:
        raise RuntimeError(f"Ant colony solver produced invalid paths: {message}")

    if best.complete:
        return SolverResult(
            solver_name="ant_colony",
            paths=best.paths,
            path_costs=path_costs,
            total_cost=sum(path_costs),
            complete=True,
            status="Algorytm mrowkowy znalazl pelny zestaw k sciezek.",
            metadata={
                "ants": solver_config.ants,
                "iterations": solver_config.iterations,
            },
        )

    return SolverResult(
        solver_name="ant_colony",
        paths=best.paths,
        path_costs=path_costs,
        total_cost=None,
        complete=False,
        status=f"Algorytm mrowkowy znalazl tylko {len(best.paths)} z {instance.k} sciezek.",
        metadata={
            "ants": solver_config.ants,
            "iterations": solver_config.iterations,
        },
    )


def _build_candidate(
    instance: ProblemInstance,
    pheromones: dict[tuple[int, int], float],
    target_distances: list[float],
    rng: random.Random,
    config: AntColonyConfig,
) -> ConcreteAntCandidate:
    blocked_vertices: set[int] = set()
    blocked_edges: set[tuple[int, int]] = set()
    paths: list[list[int]] = []

    for _ in range(instance.k):
        path = None
        for _ in range(config.max_path_attempts):
            candidate = _construct_single_path(
                instance=instance,
                pheromones=pheromones,
                target_distances=target_distances,
                rng=rng,
                config=config,
                blocked_vertices=blocked_vertices,
                blocked_edges=blocked_edges,
            )
            if candidate is not None:
                path = candidate
                break

        if path is None:
            break

        paths.append(path)
        blocked_edges.update(normalize_edge(left, right) for left, right in zip(path, path[1:]))
        if instance.disjointness == "vertex":
            blocked_vertices.update(path[1:-1])

    total_cost = sum(instance.graph.path_cost(path) for path in paths)
    return ConcreteAntCandidate(paths=paths, total_cost=total_cost, k=instance.k)


def _construct_single_path(
    instance: ProblemInstance,
    pheromones: dict[tuple[int, int], float],
    target_distances: list[float],
    rng: random.Random,
    config: AntColonyConfig,
    blocked_vertices: set[int],
    blocked_edges: set[tuple[int, int]],
) -> list[int] | None:
    current = instance.source
    path = [current]
    visited = {current}
    max_steps = instance.graph.n + 2

    for _ in range(max_steps):
        if current == instance.target:
            return path

        candidates: list[tuple[int, float]] = []
        for neighbour, weight in instance.graph.neighbors(current):
            if neighbour != instance.target and neighbour in blocked_vertices:
                continue
            edge_key = normalize_edge(current, neighbour)
            if edge_key in blocked_edges:
                continue
            if neighbour in visited:
                continue
            if target_distances[neighbour] == float("inf"):
                continue

            pheromone = pheromones.get(edge_key, 1.0)
            heuristic = 1.0 / (weight + target_distances[neighbour] + 1e-9)
            desirability = (pheromone**config.alpha) * (heuristic**config.beta)
            candidates.append((neighbour, desirability))

        if not candidates:
            return None

        if rng.random() < config.exploitation_probability:
            next_vertex = max(candidates, key=lambda item: item[1])[0]
        else:
            next_vertex = _roulette_select(rng, candidates)

        path.append(next_vertex)
        visited.add(next_vertex)
        current = next_vertex

    return path if current == instance.target else None


def _roulette_select(rng: random.Random, candidates: list[tuple[int, float]]) -> int:
    total_weight = sum(weight for _, weight in candidates)
    if total_weight <= 0:
        return rng.choice(candidates)[0]

    threshold = rng.random() * total_weight
    cumulative = 0.0
    for vertex, weight in candidates:
        cumulative += weight
        if cumulative >= threshold:
            return vertex
    return candidates[-1][0]


def _evaporate(pheromones: dict[tuple[int, int], float], evaporation: float) -> None:
    for edge in pheromones:
        pheromones[edge] = max(0.05, pheromones[edge] * (1.0 - evaporation))


def _deposit_pheromones(
    pheromones: dict[tuple[int, int], float],
    candidate: ConcreteAntCandidate,
    instance: ProblemInstance,
    factor: float,
) -> None:
    if not candidate.paths:
        return

    if candidate.complete:
        amount = factor / max(candidate.total_cost, 1e-9)
    else:
        amount = factor * (len(candidate.paths) / instance.k) / max(candidate.total_cost, 1.0)

    for path in candidate.paths:
        for left, right in zip(path, path[1:]):
            pheromones[normalize_edge(left, right)] += amount


def _is_better(candidate: ConcreteAntCandidate, incumbent: ConcreteAntCandidate) -> bool:
    if len(candidate.paths) != len(incumbent.paths):
        return len(candidate.paths) > len(incumbent.paths)
    return candidate.total_cost + 1e-12 < incumbent.total_cost
