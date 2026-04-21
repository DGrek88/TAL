from __future__ import annotations

import argparse
from pathlib import Path

from ant_solver import AntColonyConfig, solve_ant_colony
from benchmark import format_benchmark_report, format_comparison_rows, measure_solver, run_benchmark_suite
from exact_solver import ExactSolverConfig, solve_exact
from graph_generator import GeneratorConfig, PRESET_CLASSES, generate_instance
from greedy_solver import solve_greedy
from io_utils import format_quality_report, format_solver_result, instance_to_text, read_instance, write_instance


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="k najkrotszych drog rozlacznych w grafie wazonym",
    )
    parser.add_argument("--generate", action="store_true", help="Generate a random graph instance.")
    parser.add_argument("--input", type=Path, help="Path to a text file with an input graph.")
    parser.add_argument("--output", type=Path, help="Optional output path for a generated graph.")
    parser.add_argument("--run", choices=["exact", "greedy", "ant", "compare"], help="Which mode to run.")
    parser.add_argument("--benchmark", action="store_true", help="Run a benchmark suite.")

    parser.add_argument("--n", type=int, help="Number of vertices.")
    parser.add_argument("--m", type=int, help="Number of edges.")
    parser.add_argument("--k", type=int, help="Number of requested disjoint paths.")
    parser.add_argument("--source", type=int, help="Source vertex.")
    parser.add_argument("--target", type=int, help="Target vertex.")
    parser.add_argument("--min-weight", type=int, default=1, help="Minimum edge weight for generated instances.")
    parser.add_argument("--max-weight", type=int, default=20, help="Maximum edge weight for generated instances.")
    parser.add_argument("--seed", type=int, default=123, help="Random seed.")
    parser.add_argument("--disjointness", choices=["vertex", "edge"], default="vertex")
    parser.add_argument("--exact-backend", choices=["auto", "mcmf", "ilp"], default="auto")

    parser.add_argument("--ants", type=int, default=24, help="Number of ants in ant colony heuristic.")
    parser.add_argument("--iterations", type=int, default=45, help="Number of ACO iterations.")
    parser.add_argument("--ant-seed", type=int, help="Optional seed for ant colony heuristic.")
    parser.add_argument("--skip-ant", action="store_true", help="Do not run the ant colony heuristic.")

    parser.add_argument(
        "--benchmark-classes",
        nargs="+",
        choices=sorted(PRESET_CLASSES),
        default=["small", "medium", "large"],
        help="Benchmark classes to execute.",
    )
    parser.add_argument("--benchmark-repetitions", type=int, default=3, help="Number of repetitions per class.")
    parser.add_argument("--benchmark-seed", type=int, default=1000, help="Base seed for benchmark series.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.benchmark:
        benchmark_rows = run_benchmark_suite(
            class_names=args.benchmark_classes,
            repetitions=args.benchmark_repetitions,
            base_seed=args.benchmark_seed,
            disjointness=args.disjointness,
            exact_backend=args.exact_backend,
            include_ant=not args.skip_ant,
            ant_config=AntColonyConfig(
                ants=args.ants,
                iterations=args.iterations,
                seed=args.ant_seed,
            ),
        )
        print(format_benchmark_report(benchmark_rows, include_ant=not args.skip_ant))
        return

    instance = _load_or_generate_instance(args, parser)

    if args.output and args.generate:
        write_instance(instance, args.output)
        print(f"Zapisano wygenerowana instancje do: {args.output}")

    print(
        f"Instancja: n={instance.graph.n}, m={instance.graph.m}, k={instance.k}, "
        f"s={instance.source}, t={instance.target}, rozlacznosc={instance.disjointness}"
    )

    if not args.run:
        print("")
        print("Wygenerowana / wczytana instancja:")
        print(instance_to_text(instance))
        return

    ant_config = AntColonyConfig(
        ants=args.ants,
        iterations=args.iterations,
        seed=args.ant_seed,
    )

    if args.run == "exact":
        run = measure_solver(lambda current: solve_exact(current, ExactSolverConfig(args.exact_backend)), instance)
        print("")
        print(format_solver_result(run))
        return

    if args.run == "greedy":
        run = measure_solver(solve_greedy, instance)
        print("")
        print(format_solver_result(run))
        return

    if args.run == "ant":
        run = measure_solver(lambda current: solve_ant_colony(current, ant_config), instance)
        print("")
        print(format_solver_result(run))
        return

    exact_run = measure_solver(lambda current: solve_exact(current, ExactSolverConfig(args.exact_backend)), instance)
    greedy_run = measure_solver(solve_greedy, instance)

    print("")
    print(format_solver_result(exact_run))
    print("")
    print(format_solver_result(greedy_run))
    print("")
    print(format_quality_report("greedy", _quality_metrics(exact_run, greedy_run)))

    if not args.skip_ant:
        ant_run = measure_solver(lambda current: solve_ant_colony(current, ant_config), instance)
        print("")
        print(format_solver_result(ant_run))
        print("")
        print(format_quality_report("ant_colony", _quality_metrics(exact_run, ant_run)))

    runs = {"exact": exact_run, "greedy": greedy_run}
    if not args.skip_ant:
        runs["ant_colony"] = ant_run

    print("")
    print("Zestawienie skrocone:")
    print(format_comparison_rows(runs))


def _load_or_generate_instance(args: argparse.Namespace, parser: argparse.ArgumentParser):
    if args.generate and args.input:
        parser.error("Use either --generate or --input, not both.")
    if not args.generate and not args.input:
        parser.error("Choose one of: --generate or --input.")

    if args.input:
        return read_instance(args.input, disjointness=args.disjointness)

    required = {
        "n": args.n,
        "m": args.m,
        "k": args.k,
        "source": args.source,
        "target": args.target,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        parser.error(f"Missing generation arguments: {', '.join(missing)}")

    config = GeneratorConfig(
        n=args.n,
        m=args.m,
        k=args.k,
        source=args.source,
        target=args.target,
        min_weight=args.min_weight,
        max_weight=args.max_weight,
        seed=args.seed,
        disjointness=args.disjointness,
    )
    return generate_instance(config)


def _quality_metrics(exact_run, heuristic_run):
    from io_utils import build_quality_metrics

    return build_quality_metrics(exact_run.result, heuristic_run.result)


if __name__ == "__main__":
    main()
