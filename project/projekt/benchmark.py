from __future__ import annotations

import time
import tracemalloc
from dataclasses import dataclass
from statistics import mean
from typing import Callable

from ant_solver import AntColonyConfig, solve_ant_colony
from exact_solver import ExactSolverConfig, solve_exact
from graph_generator import GeneratorConfig, preset_config, generate_instance
from greedy_solver import solve_greedy
from io_utils import MeasuredRun, ProblemInstance, SolverResult, build_quality_metrics, format_number


SolverCallable = Callable[[ProblemInstance], SolverResult]


@dataclass(frozen=True)
class BenchmarkRow:
    class_name: str
    repetition: int
    n: int
    m: int
    k: int
    seed: int
    exact_complete: bool
    exact_cost: float | None
    exact_time: float
    exact_memory_kib: float
    greedy_complete: bool
    greedy_cost: float | None
    greedy_time: float
    greedy_memory_kib: float
    greedy_ratio: float | None
    ant_complete: bool | None = None
    ant_cost: float | None = None
    ant_time: float | None = None
    ant_memory_kib: float | None = None
    ant_ratio: float | None = None


def measure_solver(solver: SolverCallable, instance: ProblemInstance) -> MeasuredRun:
    tracemalloc.start()
    start = time.perf_counter()
    try:
        result = solver(instance)
    finally:
        elapsed = time.perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    return MeasuredRun(result=result, elapsed_seconds=elapsed, peak_memory_bytes=peak)


def run_comparison(
    instance: ProblemInstance,
    exact_backend: str = "auto",
    ant_config: AntColonyConfig | None = None,
    include_ant: bool = True,
) -> dict[str, MeasuredRun]:
    exact_run = measure_solver(lambda current: solve_exact(current, ExactSolverConfig(backend=exact_backend)), instance)
    greedy_run = measure_solver(solve_greedy, instance)

    comparison: dict[str, MeasuredRun] = {
        "exact": exact_run,
        "greedy": greedy_run,
    }

    if include_ant:
        ant_run = measure_solver(lambda current: solve_ant_colony(current, ant_config), instance)
        comparison["ant_colony"] = ant_run

    return comparison


def run_benchmark_suite(
    class_names: list[str],
    repetitions: int = 3,
    base_seed: int = 1000,
    disjointness: str = "vertex",
    exact_backend: str = "auto",
    include_ant: bool = True,
    ant_config: AntColonyConfig | None = None,
) -> list[BenchmarkRow]:
    rows: list[BenchmarkRow] = []

    for class_index, class_name in enumerate(class_names):
        for repetition in range(1, repetitions + 1):
            seed = base_seed + class_index * 100 + repetition
            config = preset_config(class_name, seed=seed, disjointness=disjointness)
            instance = generate_instance(config)
            comparison = run_comparison(
                instance=instance,
                exact_backend=exact_backend,
                ant_config=ant_config,
                include_ant=include_ant,
            )

            exact_run = comparison["exact"]
            greedy_run = comparison["greedy"]
            greedy_metrics = build_quality_metrics(exact_run.result, greedy_run.result)

            row = BenchmarkRow(
                class_name=class_name,
                repetition=repetition,
                n=config.n,
                m=config.m,
                k=config.k,
                seed=seed,
                exact_complete=exact_run.result.complete,
                exact_cost=exact_run.result.total_cost,
                exact_time=exact_run.elapsed_seconds,
                exact_memory_kib=exact_run.peak_memory_bytes / 1024,
                greedy_complete=greedy_run.result.complete,
                greedy_cost=greedy_run.result.total_cost,
                greedy_time=greedy_run.elapsed_seconds,
                greedy_memory_kib=greedy_run.peak_memory_bytes / 1024,
                greedy_ratio=_safe_ratio(greedy_metrics.get("ratio")),
            )

            if include_ant and "ant_colony" in comparison:
                ant_run = comparison["ant_colony"]
                ant_metrics = build_quality_metrics(exact_run.result, ant_run.result)
                row = BenchmarkRow(
                    class_name=row.class_name,
                    repetition=row.repetition,
                    n=row.n,
                    m=row.m,
                    k=row.k,
                    seed=row.seed,
                    exact_complete=row.exact_complete,
                    exact_cost=row.exact_cost,
                    exact_time=row.exact_time,
                    exact_memory_kib=row.exact_memory_kib,
                    greedy_complete=row.greedy_complete,
                    greedy_cost=row.greedy_cost,
                    greedy_time=row.greedy_time,
                    greedy_memory_kib=row.greedy_memory_kib,
                    greedy_ratio=row.greedy_ratio,
                    ant_complete=ant_run.result.complete,
                    ant_cost=ant_run.result.total_cost,
                    ant_time=ant_run.elapsed_seconds,
                    ant_memory_kib=ant_run.peak_memory_bytes / 1024,
                    ant_ratio=_safe_ratio(ant_metrics.get("ratio")),
                )

            rows.append(row)

    return rows


def format_comparison_rows(runs: dict[str, MeasuredRun]) -> str:
    lines: list[str] = []
    exact_result = runs["exact"].result

    for name, run in runs.items():
        lines.append(
            f"{name:10} | pelne={str(run.result.complete):5} | koszt={format_number(run.result.total_cost):>8} "
            f"| czas={run.elapsed_seconds:>9.6f} s | pamiec={run.peak_memory_bytes / 1024:>9.2f} KiB"
        )
        if name != "exact":
            metrics = build_quality_metrics(exact_result, run.result)
            lines.append(
                f"  -> ratio={format_number(metrics['ratio'])}, roznica={format_number(metrics['difference_abs'])}, "
                f"uwaga={metrics['note']}"
            )

    return "\n".join(lines)


def format_benchmark_report(rows: list[BenchmarkRow], include_ant: bool = True) -> str:
    if not rows:
        return "Brak danych benchmarkowych."

    header = [
        "klasa    rep   n   m   k   exact_cost   greedy_cost   greedy_ratio   exact_t[s]   greedy_t[s]",
    ]
    if include_ant:
        header[0] += "   ant_cost   ant_ratio   ant_t[s]"

    lines = header
    for row in rows:
        line = (
            f"{row.class_name:<8} {row.repetition:>3} {row.n:>3} {row.m:>3} {row.k:>3} "
            f"{format_number(row.exact_cost):>11} {format_number(row.greedy_cost):>12} "
            f"{format_number(row.greedy_ratio):>13} {row.exact_time:>11.6f} {row.greedy_time:>12.6f}"
        )
        if include_ant:
            line += (
                f" {format_number(row.ant_cost):>10} {format_number(row.ant_ratio):>10} "
                f"{(row.ant_time or 0.0):>10.6f}"
            )
        lines.append(line)

    lines.append("")
    lines.append("Podsumowanie srednie dla klas:")
    for class_name in sorted({row.class_name for row in rows}):
        class_rows = [row for row in rows if row.class_name == class_name]
        lines.append(_format_class_summary(class_name, class_rows, include_ant))

    return "\n".join(lines)


def benchmark_instance_from_config(config: GeneratorConfig) -> tuple[ProblemInstance, dict[str, MeasuredRun]]:
    instance = generate_instance(config)
    comparison = run_comparison(instance)
    return instance, comparison


def _format_class_summary(class_name: str, rows: list[BenchmarkRow], include_ant: bool) -> str:
    greedy_ratios = [row.greedy_ratio for row in rows if row.greedy_ratio is not None]
    ant_ratios = [row.ant_ratio for row in rows if row.ant_ratio is not None]

    summary = (
        f"{class_name}: exact_t={mean(row.exact_time for row in rows):.6f}s, "
        f"greedy_t={mean(row.greedy_time for row in rows):.6f}s, "
        f"greedy_ratio={format_number(mean(greedy_ratios) if greedy_ratios else None)}, "
        f"greedy_success={sum(row.greedy_complete for row in rows)}/{len(rows)}"
    )

    if include_ant:
        ant_times = [row.ant_time for row in rows if row.ant_time is not None]
        success = sum(1 for row in rows if row.ant_complete)
        summary += (
            f", ant_t={mean(ant_times):.6f}s" if ant_times else ", ant_t=-"
        )
        summary += (
            f", ant_ratio={format_number(mean(ant_ratios) if ant_ratios else None)}, "
            f"ant_success={success}/{len(rows)}"
        )

    return summary


def _safe_ratio(value: object) -> float | None:
    return float(value) if isinstance(value, (float, int)) else None
