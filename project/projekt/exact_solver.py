from __future__ import annotations

import heapq
from dataclasses import dataclass

from io_utils import ProblemInstance, SolverResult, validate_paths

try:
    import pulp
except ImportError:  # pragma: no cover - optional dependency
    pulp = None


@dataclass(frozen=True)
class ExactSolverConfig:
    backend: str = "auto"


@dataclass(frozen=True)
class SplitArc:
    tail: int
    head: int
    capacity: int
    cost: float
    arc_type: str
    original_u: int | None = None
    original_v: int | None = None


@dataclass
class ResidualEdge:
    to: int
    rev: int
    capacity: int
    cost: float
    original_capacity: int
    arc_type: str
    original_u: int | None = None
    original_v: int | None = None


class MinCostMaxFlow:
    """Successive shortest augmenting path algorithm with potentials."""

    def __init__(self, node_count: int) -> None:
        self.graph: list[list[ResidualEdge]] = [[] for _ in range(node_count)]

    def add_edge(
        self,
        tail: int,
        head: int,
        capacity: int,
        cost: float,
        arc_type: str,
        original_u: int | None = None,
        original_v: int | None = None,
    ) -> None:
        forward = ResidualEdge(
            to=head,
            rev=len(self.graph[head]),
            capacity=capacity,
            cost=cost,
            original_capacity=capacity,
            arc_type=arc_type,
            original_u=original_u,
            original_v=original_v,
        )
        backward = ResidualEdge(
            to=tail,
            rev=len(self.graph[tail]),
            capacity=0,
            cost=-cost,
            original_capacity=0,
            arc_type="reverse",
        )
        self.graph[tail].append(forward)
        self.graph[head].append(backward)

    def run(self, source: int, sink: int, required_flow: int) -> tuple[int, float]:
        node_count = len(self.graph)
        flow = 0
        total_cost = 0.0
        potentials = [0.0] * node_count

        while flow < required_flow:
            distances = [float("inf")] * node_count
            previous_node = [-1] * node_count
            previous_edge = [-1] * node_count
            distances[source] = 0.0
            queue: list[tuple[float, int]] = [(0.0, source)]

            while queue:
                distance, vertex = heapq.heappop(queue)
                if distance > distances[vertex] + 1e-12:
                    continue

                for edge_index, edge in enumerate(self.graph[vertex]):
                    if edge.capacity <= 0:
                        continue

                    reduced_cost = edge.cost + potentials[vertex] - potentials[edge.to]
                    candidate = distance + reduced_cost
                    if candidate + 1e-12 < distances[edge.to]:
                        distances[edge.to] = candidate
                        previous_node[edge.to] = vertex
                        previous_edge[edge.to] = edge_index
                        heapq.heappush(queue, (candidate, edge.to))

            if distances[sink] == float("inf"):
                break

            for vertex in range(node_count):
                if distances[vertex] < float("inf"):
                    potentials[vertex] += distances[vertex]

            pushed = required_flow - flow
            vertex = sink
            while vertex != source:
                prev_vertex = previous_node[vertex]
                if prev_vertex == -1:
                    pushed = 0
                    break
                edge = self.graph[prev_vertex][previous_edge[vertex]]
                pushed = min(pushed, edge.capacity)
                vertex = prev_vertex

            if pushed == 0:
                break

            vertex = sink
            while vertex != source:
                prev_vertex = previous_node[vertex]
                edge = self.graph[prev_vertex][previous_edge[vertex]]
                reverse = self.graph[vertex][edge.rev]
                edge.capacity -= pushed
                reverse.capacity += pushed
                total_cost += pushed * edge.cost
                vertex = prev_vertex

            flow += pushed

        return flow, total_cost


def solve_exact(instance: ProblemInstance, config: ExactSolverConfig | None = None) -> SolverResult:
    solver_config = config or ExactSolverConfig()
    backend = solver_config.backend.lower()

    if backend not in {"auto", "mcmf", "ilp"}:
        raise ValueError("Exact backend must be one of: auto, mcmf, ilp.")

    if backend == "mcmf":
        return _solve_with_mcmf(instance)
    if backend == "ilp":
        return _solve_with_ilp(instance)

    if pulp is not None:
        try:
            return _solve_with_ilp(instance)
        except Exception:  # pragma: no cover - safety fallback
            return _solve_with_mcmf(instance)
    return _solve_with_mcmf(instance)


def _build_split_arcs(instance: ProblemInstance) -> tuple[int, int, int, list[SplitArc]]:
    def node_in(vertex: int) -> int:
        return 2 * vertex

    def node_out(vertex: int) -> int:
        return 2 * vertex + 1

    node_count = 2 * instance.graph.n + 2
    source_node = 2 * instance.graph.n
    sink_node = source_node + 1
    arcs: list[SplitArc] = []

    arcs.append(SplitArc(source_node, node_in(instance.source), instance.k, 0.0, "source"))
    arcs.append(SplitArc(node_out(instance.target), sink_node, instance.k, 0.0, "sink"))

    for vertex in range(instance.graph.n):
        if instance.disjointness == "vertex" and vertex not in {instance.source, instance.target}:
            capacity = 1
        else:
            capacity = instance.k
        arcs.append(SplitArc(node_in(vertex), node_out(vertex), capacity, 0.0, "vertex"))

    for edge in instance.graph.edges:
        arcs.append(
            SplitArc(
                node_out(edge.u),
                node_in(edge.v),
                1,
                edge.weight,
                "transport",
                original_u=edge.u,
                original_v=edge.v,
            )
        )
        arcs.append(
            SplitArc(
                node_out(edge.v),
                node_in(edge.u),
                1,
                edge.weight,
                "transport",
                original_u=edge.v,
                original_v=edge.u,
            )
        )

    return node_count, source_node, sink_node, arcs


def _solve_with_mcmf(instance: ProblemInstance) -> SolverResult:
    node_count, source_node, sink_node, arcs = _build_split_arcs(instance)
    network = MinCostMaxFlow(node_count)

    for arc in arcs:
        network.add_edge(
            tail=arc.tail,
            head=arc.head,
            capacity=arc.capacity,
            cost=arc.cost,
            arc_type=arc.arc_type,
            original_u=arc.original_u,
            original_v=arc.original_v,
        )

    flow, total_cost = network.run(source_node, sink_node, instance.k)
    if flow < instance.k:
        return SolverResult(
            solver_name="exact",
            paths=[],
            path_costs=[],
            total_cost=None,
            complete=False,
            status="Nie istnieje pelny zestaw k rozlacznych sciezek.",
            metadata={"backend": "mcmf", "flow_sent": flow},
        )

    used_transport_arcs: list[tuple[int, int]] = []
    for bucket in network.graph:
        for edge in bucket:
            used_flow = edge.original_capacity - edge.capacity
            if edge.arc_type == "transport" and used_flow > 0:
                for _ in range(used_flow):
                    assert edge.original_u is not None and edge.original_v is not None
                    used_transport_arcs.append((edge.original_u, edge.original_v))

    paths = _extract_paths_from_transport(instance, used_transport_arcs)
    path_costs = [instance.graph.path_cost(path) for path in paths]
    valid, message = validate_paths(instance, paths)
    if not valid:
        raise RuntimeError(f"Exact MCMF solver produced invalid paths: {message}")

    return SolverResult(
        solver_name="exact",
        paths=paths,
        path_costs=path_costs,
        total_cost=total_cost,
        complete=len(paths) == instance.k,
        status="Znaleziono optymalny zestaw k rozlacznych sciezek.",
        metadata={"backend": "mcmf"},
    )


def _solve_with_ilp(instance: ProblemInstance) -> SolverResult:
    if pulp is None:
        raise RuntimeError("PuLP is not installed. Use backend='mcmf' or install requirements.")

    node_count, source_node, sink_node, arcs = _build_split_arcs(instance)
    problem = pulp.LpProblem("k_disjoint_paths", pulp.LpMinimize)

    variables: dict[int, pulp.LpVariable] = {}
    outgoing: dict[int, list[int]] = {node: [] for node in range(node_count)}
    incoming: dict[int, list[int]] = {node: [] for node in range(node_count)}

    for index, arc in enumerate(arcs):
        variables[index] = pulp.LpVariable(
            f"x_{index}",
            lowBound=0,
            upBound=arc.capacity,
            cat=pulp.LpInteger,
        )
        outgoing[arc.tail].append(index)
        incoming[arc.head].append(index)

    problem += pulp.lpSum(arc.cost * variables[index] for index, arc in enumerate(arcs))

    for node in range(node_count):
        balance = 0
        if node == source_node:
            balance = instance.k
        elif node == sink_node:
            balance = -instance.k

        problem += (
            pulp.lpSum(variables[index] for index in outgoing[node])
            - pulp.lpSum(variables[index] for index in incoming[node])
            == balance
        )

    status_code = problem.solve(pulp.PULP_CBC_CMD(msg=False))
    status_name = pulp.LpStatus.get(status_code, "Unknown")
    if status_name != "Optimal":
        return SolverResult(
            solver_name="exact",
            paths=[],
            path_costs=[],
            total_cost=None,
            complete=False,
            status="Nie istnieje pelny zestaw k rozlacznych sciezek.",
            metadata={"backend": "ilp", "lp_status": status_name},
        )

    used_transport_arcs: list[tuple[int, int]] = []
    for index, arc in enumerate(arcs):
        value = int(round(float(variables[index].value() or 0.0)))
        if arc.arc_type == "transport" and value > 0:
            for _ in range(value):
                assert arc.original_u is not None and arc.original_v is not None
                used_transport_arcs.append((arc.original_u, arc.original_v))

    paths = _extract_paths_from_transport(instance, used_transport_arcs)
    path_costs = [instance.graph.path_cost(path) for path in paths]
    valid, message = validate_paths(instance, paths)
    if not valid:
        raise RuntimeError(f"Exact ILP solver produced invalid paths: {message}")

    total_cost = float(pulp.value(problem.objective))
    return SolverResult(
        solver_name="exact",
        paths=paths,
        path_costs=path_costs,
        total_cost=total_cost,
        complete=len(paths) == instance.k,
        status="Znaleziono optymalny zestaw k rozlacznych sciezek.",
        metadata={"backend": "ilp", "lp_status": status_name},
    )


def _extract_paths_from_transport(instance: ProblemInstance, arcs: list[tuple[int, int]]) -> list[list[int]]:
    outgoing: dict[int, list[int]] = {}
    for start, end in arcs:
        outgoing.setdefault(start, []).append(end)

    for neighbours in outgoing.values():
        neighbours.sort(reverse=True)

    paths: list[list[int]] = []
    for _ in range(instance.k):
        if instance.source not in outgoing or not outgoing[instance.source]:
            break

        current = instance.source
        path = [current]
        visited = {current}

        while current != instance.target:
            if current not in outgoing or not outgoing[current]:
                raise RuntimeError("Flow decomposition failed: incomplete walk.")

            next_vertex = outgoing[current].pop()
            if not outgoing[current]:
                outgoing.pop(current)

            if next_vertex in visited:
                raise RuntimeError("Flow decomposition failed: cycle detected.")

            path.append(next_vertex)
            visited.add(next_vertex)
            current = next_vertex

        paths.append(path)

    return paths
