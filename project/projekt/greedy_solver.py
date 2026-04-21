from __future__ import annotations

import heapq

from io_utils import ProblemInstance, SolverResult, normalize_edge, validate_paths


def shortest_distances_from_target(instance: ProblemInstance) -> list[float]:
    """Compute distances to target for heuristic guidance."""
    distances = [float("inf")] * instance.graph.n
    distances[instance.target] = 0.0
    queue: list[tuple[float, int]] = [(0.0, instance.target)]

    while queue:
        current_distance, vertex = heapq.heappop(queue)
        if current_distance > distances[vertex] + 1e-12:
            continue

        for neighbour, weight in instance.graph.neighbors(vertex):
            candidate = current_distance + weight
            if candidate + 1e-12 < distances[neighbour]:
                distances[neighbour] = candidate
                heapq.heappush(queue, (candidate, neighbour))

    return distances


def shortest_path_with_filters(
    instance: ProblemInstance,
    blocked_vertices: set[int] | None = None,
    blocked_edges: set[tuple[int, int]] | None = None,
) -> list[int] | None:
    blocked_vertices = blocked_vertices or set()
    blocked_edges = blocked_edges or set()

    distances = [float("inf")] * instance.graph.n
    previous: dict[int, int] = {}
    distances[instance.source] = 0.0
    queue: list[tuple[float, int]] = [(0.0, instance.source)]

    while queue:
        current_distance, vertex = heapq.heappop(queue)
        if current_distance > distances[vertex] + 1e-12:
            continue
        if vertex == instance.target:
            break

        for neighbour, weight in instance.graph.neighbors(vertex):
            if neighbour != instance.target and neighbour in blocked_vertices:
                continue
            if normalize_edge(vertex, neighbour) in blocked_edges:
                continue

            candidate = current_distance + weight
            if candidate + 1e-12 < distances[neighbour]:
                distances[neighbour] = candidate
                previous[neighbour] = vertex
                heapq.heappush(queue, (candidate, neighbour))

    if distances[instance.target] == float("inf"):
        return None

    path = [instance.target]
    current = instance.target
    while current != instance.source:
        current = previous[current]
        path.append(current)
    path.reverse()
    return path


def solve_greedy(instance: ProblemInstance) -> SolverResult:
    blocked_vertices: set[int] = set()
    blocked_edges: set[tuple[int, int]] = set()
    paths: list[list[int]] = []

    for _ in range(instance.k):
        path = shortest_path_with_filters(
            instance=instance,
            blocked_vertices=blocked_vertices,
            blocked_edges=blocked_edges,
        )
        if path is None:
            break

        paths.append(path)
        blocked_edges.update(normalize_edge(left, right) for left, right in zip(path, path[1:]))
        if instance.disjointness == "vertex":
            blocked_vertices.update(path[1:-1])

    path_costs = [instance.graph.path_cost(path) for path in paths]
    complete = len(paths) == instance.k
    valid, message = validate_paths(instance, paths)
    if not valid:
        raise RuntimeError(f"Greedy solver produced invalid paths: {message}")

    if complete:
        status = "Heurystyka zachlanna znalazla pelny zestaw k sciezek."
        total_cost = sum(path_costs)
    else:
        status = f"Heurystyka zachlanna znalazla tylko {len(paths)} z {instance.k} sciezek."
        total_cost = None

    return SolverResult(
        solver_name="greedy",
        paths=paths,
        path_costs=path_costs,
        total_cost=total_cost,
        complete=complete,
        status=status,
        metadata={},
    )
