from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


DisjointnessMode = str


def normalize_edge(u: int, v: int) -> tuple[int, int]:
    """Return a canonical representation of an undirected edge."""
    return (u, v) if u < v else (v, u)


def format_number(value: float | int | None, digits: int = 4) -> str:
    """Format numeric values in a user-friendly way."""
    if value is None:
        return "-"
    if isinstance(value, int):
        return str(value)
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.{digits}f}"


@dataclass(frozen=True)
class Edge:
    u: int
    v: int
    weight: float


class WeightedGraph:
    """Simple adjacency-list representation of an undirected weighted graph."""

    def __init__(self, n: int, edges: Iterable[Edge]) -> None:
        if n < 2:
            raise ValueError("Graph must contain at least 2 vertices.")

        self.n = n
        self.edges: list[Edge] = []
        self._adjacency: list[list[tuple[int, float]]] = [[] for _ in range(n)]
        self._weights: dict[tuple[int, int], float] = {}

        for edge in edges:
            self._add_edge(edge)

    def _add_edge(self, edge: Edge) -> None:
        if not (0 <= edge.u < self.n and 0 <= edge.v < self.n):
            raise ValueError(f"Edge {edge.u}-{edge.v} is outside vertex range 0..{self.n - 1}.")
        if edge.u == edge.v:
            raise ValueError("Self-loops are not allowed.")
        if edge.weight <= 0:
            raise ValueError("Edge weights must be positive.")

        key = normalize_edge(edge.u, edge.v)
        if key in self._weights:
            raise ValueError(f"Duplicate edge detected: {key[0]}-{key[1]}.")

        self._weights[key] = edge.weight
        self.edges.append(edge)
        self._adjacency[edge.u].append((edge.v, edge.weight))
        self._adjacency[edge.v].append((edge.u, edge.weight))

    @property
    def m(self) -> int:
        return len(self.edges)

    def neighbors(self, vertex: int) -> list[tuple[int, float]]:
        return self._adjacency[vertex]

    def degree(self, vertex: int) -> int:
        return len(self._adjacency[vertex])

    def has_edge(self, u: int, v: int) -> bool:
        return normalize_edge(u, v) in self._weights

    def edge_weight(self, u: int, v: int) -> float:
        key = normalize_edge(u, v)
        if key not in self._weights:
            raise KeyError(f"Edge {u}-{v} does not exist in the graph.")
        return self._weights[key]

    def path_cost(self, path: list[int]) -> float:
        if len(path) < 2:
            return 0.0
        return sum(self.edge_weight(path[index], path[index + 1]) for index in range(len(path) - 1))


@dataclass(frozen=True)
class ProblemInstance:
    graph: WeightedGraph
    k: int
    source: int
    target: int
    disjointness: DisjointnessMode = "vertex"
    name: str | None = None

    def __post_init__(self) -> None:
        if self.k <= 2:
            raise ValueError("The assignment assumes k > 2.")
        if not (0 <= self.source < self.graph.n and 0 <= self.target < self.graph.n):
            raise ValueError("Source and target must be valid vertex identifiers.")
        if self.source == self.target:
            raise ValueError("Source and target must be different vertices.")
        if self.disjointness not in {"vertex", "edge"}:
            raise ValueError("Disjointness must be either 'vertex' or 'edge'.")


@dataclass
class SolverResult:
    solver_name: str
    paths: list[list[int]]
    path_costs: list[float]
    total_cost: float | None
    complete: bool
    status: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MeasuredRun:
    result: SolverResult
    elapsed_seconds: float
    peak_memory_bytes: int


def path_to_text(path: list[int]) -> str:
    return " -> ".join(str(vertex) for vertex in path)


def instance_to_text(instance: ProblemInstance) -> str:
    lines = [
        f"{instance.graph.n} {instance.graph.m} {instance.k} {instance.source} {instance.target}",
    ]
    for edge in sorted(instance.graph.edges, key=lambda item: (min(item.u, item.v), max(item.u, item.v))):
        lines.append(f"{edge.u} {edge.v} {format_number(edge.weight)}")
    return "\n".join(lines)


def write_instance(instance: ProblemInstance, path: str | Path) -> None:
    Path(path).write_text(instance_to_text(instance) + "\n", encoding="utf-8")


def read_instance(path: str | Path, disjointness: DisjointnessMode = "vertex") -> ProblemInstance:
    raw_lines = Path(path).read_text(encoding="utf-8").splitlines()
    lines = [line.strip() for line in raw_lines if line.strip() and not line.strip().startswith("#")]
    if not lines:
        raise ValueError("Input file is empty.")

    header = lines[0].split()
    if len(header) != 5:
        raise ValueError("The first line must contain: n m k s t")

    n, m, k, source, target = map(int, header)
    edges: list[Edge] = []
    for index, line in enumerate(lines[1:], start=2):
        parts = line.split()
        if len(parts) != 3:
            raise ValueError(f"Line {index}: expected 'u v w'.")
        u, v = map(int, parts[:2])
        weight = float(parts[2])
        edges.append(Edge(u=u, v=v, weight=weight))

    if len(edges) != m:
        raise ValueError(f"Header declares {m} edges, but file contains {len(edges)}.")

    graph = WeightedGraph(n=n, edges=edges)
    return ProblemInstance(
        graph=graph,
        k=k,
        source=source,
        target=target,
        disjointness=disjointness,
        name=str(Path(path)),
    )


def validate_paths(instance: ProblemInstance, paths: list[list[int]]) -> tuple[bool, str]:
    used_vertices: set[int] = set()
    used_edges: set[tuple[int, int]] = set()
    seen_paths: set[tuple[int, ...]] = set()

    for index, path in enumerate(paths, start=1):
        if len(path) < 2:
            return False, f"Path {index} is too short."
        if path[0] != instance.source or path[-1] != instance.target:
            return False, f"Path {index} does not connect source to target."
        if len(set(path)) != len(path):
            return False, f"Path {index} is not simple."
        path_key = tuple(path)
        if path_key in seen_paths:
            return False, "Returned paths are duplicated."
        seen_paths.add(path_key)

        for left, right in zip(path, path[1:]):
            if not instance.graph.has_edge(left, right):
                return False, f"Path {index} uses a non-existing edge {left}-{right}."

        internal_edges = {normalize_edge(left, right) for left, right in zip(path, path[1:])}
        if used_edges & internal_edges:
            return False, "Returned paths reuse an edge."
        used_edges.update(internal_edges)

        if instance.disjointness == "vertex":
            internal_vertices = set(path[1:-1])
            if used_vertices & internal_vertices:
                return False, "Returned paths are not vertex-disjoint."
            used_vertices.update(internal_vertices)

    return True, "ok"


def build_quality_metrics(exact: SolverResult, heuristic: SolverResult) -> dict[str, float | bool | None | str]:
    metrics: dict[str, float | bool | None | str] = {
        "exact_complete": exact.complete,
        "heur_complete": heuristic.complete,
        "cost_exact": exact.total_cost,
        "cost_heur": heuristic.total_cost,
        "difference_abs": None,
        "ratio": None,
        "note": "",
    }

    if exact.complete and heuristic.complete and exact.total_cost is not None and heuristic.total_cost is not None:
        difference = abs(heuristic.total_cost - exact.total_cost)
        metrics["difference_abs"] = difference
        metrics["ratio"] = heuristic.total_cost / exact.total_cost
        metrics["note"] = "Heurystyka znalazla pelne rozwiazanie i mozna porownac koszty."
        return metrics

    if not exact.complete and not heuristic.complete:
        metrics["note"] = "Ani solver dokladny, ani heurystyka nie znalazly pelnego zestawu k sciezek."
    elif exact.complete and not heuristic.complete:
        metrics["note"] = "Rozwiazanie dokladne istnieje, ale heurystyka nie znalazla pelnych k sciezek."
    elif not exact.complete and heuristic.complete:
        metrics["note"] = (
            "Heurystyka zwrocila pelny zestaw sciezek, ale solver dokladny go nie potwierdzil. "
            "To sygnal do dodatkowej weryfikacji."
        )
    else:
        metrics["note"] = "Nie mozna policzyc ratio, bo przynajmniej jeden solver nie zwrocil pelnego kosztu."

    return metrics


def format_solver_result(run: MeasuredRun) -> str:
    result = run.result
    lines = [
        f"Solver: {result.solver_name}",
        f"Status: {result.status}",
        f"Pelne k sciezek: {'TAK' if result.complete else 'NIE'}",
        "Sciezki:",
    ]

    if result.paths:
        for index, path in enumerate(result.paths, start=1):
            cost = result.path_costs[index - 1] if index - 1 < len(result.path_costs) else None
            lines.append(f"  {index}. {path_to_text(path)} | koszt = {format_number(cost)}")
    else:
        lines.append("  brak")

    lines.extend(
        [
            f"Laczny koszt: {format_number(result.total_cost)}",
            f"Czas: {run.elapsed_seconds:.6f} s",
            f"Pamiec peak (tracemalloc): {run.peak_memory_bytes / 1024:.2f} KiB",
        ]
    )

    if result.metadata:
        for key, value in sorted(result.metadata.items()):
            lines.append(f"{key}: {value}")

    return "\n".join(lines)


def format_quality_report(label: str, metrics: dict[str, float | bool | None | str]) -> str:
    return "\n".join(
        [
            f"Porownanie heurystyki: {label}",
            f"  koszt_exact: {format_number(metrics['cost_exact'])}",
            f"  koszt_heur: {format_number(metrics['cost_heur'])}",
            f"  roznica_bezwzgledna: {format_number(metrics['difference_abs'])}",
            f"  ratio: {format_number(metrics['ratio'])}",
            f"  heurystyka_pelna: {'TAK' if metrics['heur_complete'] else 'NIE'}",
            f"  uwaga: {metrics['note']}",
        ]
    )
