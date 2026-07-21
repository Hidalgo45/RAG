import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import requests
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import AppConfig
from .ingest import ingest_documents
from .rag import PersonalRAG
from .roles import get_role, menu_roles

console = Console()


def ollama_tags(config: AppConfig) -> set[str]:
    response = requests.get(f"{config.ollama_base_url}/api/tags", timeout=10)
    response.raise_for_status()
    return {item["name"] for item in response.json().get("models", [])}


def model_present(tags: set[str], model: str) -> bool:
    return any(name == model or name.startswith(model + ":") for name in tags)


def command_check(config: AppConfig) -> int:
    config.ensure_directories()
    table = Table(title="Verificación del sistema")
    table.add_column("Componente")
    table.add_column("Estado")
    table.add_column("Detalle")
    table.add_row("Python", "OK", sys.version.split()[0])

    try:
        tags = ollama_tags(config)
        table.add_row("Ollama API", "OK", config.ollama_base_url)
        table.add_row("Modelo generativo", "OK" if model_present(tags, config.llm_model) else "FALTA", config.llm_model)
        table.add_row("Modelo embeddings", "OK" if model_present(tags, config.embed_model) else "FALTA", config.embed_model)
    except Exception as error:
        table.add_row("Ollama API", "ERROR", str(error))

    usage = shutil.disk_usage(Path.cwd())
    free_gb = usage.free / (1024 ** 3)
    table.add_row(
        "Espacio libre",
        "OK" if free_gb >= config.min_free_disk_gb else "ADVERTENCIA",
        f"{free_gb:.2f} GB",
    )
    docs = len([p for p in config.data_dir.rglob("*") if p.is_file() and not p.name.startswith(".")])
    table.add_row("Documentos", "OK" if docs else "FALTA", str(docs))
    console.print(table)
    return 0


def command_ingest(config: AppConfig, rebuild: bool) -> int:
    try:
        changed = ingest_documents(config, rebuild=rebuild)
        console.print("[green]Ingestión completada.[/green]" if changed
                      else "[yellow]No se detectaron cambios.[/yellow]")
        return 0
    except Exception as error:
        console.print(f"[red]Error de ingestión:[/red] {error}")
        return 1


def select_role() -> dict:
    console.print(Panel(menu_roles(), title="¿Quién realiza la consulta?"))
    return get_role(console.input("Seleccione una opción: "))


def command_chat(config: AppConfig) -> int:
    role = select_role()
    debug = config.debug_sources
    try:
        rag = PersonalRAG(config)
    except Exception as error:
        console.print(f"[red]{error}[/red]")
        return 1

    console.print(Panel("Preguntas libres. Comandos: /salir, /rol, /debug",
                        title=f"RAG personal | Rol: {role['label']}"))
    try:
        while True:
            query = console.input("\n[bold cyan]Pregunta>[/bold cyan] ").strip()
            if not query:
                continue
            if query.lower() == "/salir":
                break
            if query.lower() == "/rol":
                role = select_role()
                continue
            if query.lower() == "/debug":
                debug = not debug
                console.print(f"Fuentes: {'activadas' if debug else 'desactivadas'}")
                continue

            start = time.perf_counter()
            result = rag.ask(query, role)
            elapsed = time.perf_counter() - start
            console.print(Panel(result["answer"], title=f"Respuesta | {elapsed:.2f}s"))
            if debug:
                for source in result["sources"]:
                    console.print(
                        f"[dim]{source['file_name']} | score={source['score']} | {source['text']}[/dim]"
                    )
    finally:
        rag.close()
    return 0


def command_evaluate(config: AppConfig) -> int:
    cases = json.loads(Path("evaluation/questions.json").read_text(encoding="utf-8"))
    rag = PersonalRAG(config)
    role = get_role("5")
    passed = 0
    durations = []
    try:
        for case in cases:
            start = time.perf_counter()
            result = rag.ask(case["question"], role)
            duration = time.perf_counter() - start
            durations.append(duration)
            answer = result["answer"].lower()
            ok = all(t.lower() in answer for t in case.get("expected_terms", []))
            ok = ok and all(t.lower() not in answer for t in case.get("forbidden_terms", []))
            passed += int(ok)
            console.print(
                f"{'[green]OK[/green]' if ok else '[red]FALLO[/red]'} "
                f"{case['id']} | {duration:.2f}s | {case['question']}"
            )
    finally:
        rag.close()

    average = sum(durations) / len(durations) if durations else 0
    console.print(f"\nAprobadas: {passed}/{len(cases)}")
    console.print(f"Tiempo promedio: {average:.2f}s")
    return 0 if passed == len(cases) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RAG personal local")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    ingest = sub.add_parser("ingest")
    ingest.add_argument("--rebuild", action="store_true")
    sub.add_parser("chat")
    sub.add_parser("evaluate")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = AppConfig()
    if args.command == "check":
        return command_check(config)
    if args.command == "ingest":
        return command_ingest(config, args.rebuild)
    if args.command == "chat":
        return command_chat(config)
    if args.command == "evaluate":
        return command_evaluate(config)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
