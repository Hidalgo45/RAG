"""
CLI de consola para probar autenticación y autorización antes de integrarlo a la web.

Uso:
    python -m src.auth_cli bootstrap-admin
    python -m src.auth_cli register
    python -m src.auth_cli login
    python -m src.auth_cli check-permission
    python -m src.auth_cli revoke-user
    python -m src.auth_cli audit
    python -m src.auth_cli test-authorization
"""

import argparse
import getpass
import sys

from rich.console import Console
from rich.table import Table

from .auth import (
    AuthError,
    AuthDB,
    RESOURCES,
    ROLE_NAMES,
    authenticate,
    bootstrap_admin,
    check_permission,
    get_audit_log,
    register_user,
    revoke_user,
    validate_session,
)

console = Console()


def cmd_bootstrap_admin(db: AuthDB) -> int:
    console.print("[bold]Creación del primer administrador[/bold]")
    username = input("Usuario admin: ").strip()
    password = getpass.getpass("Contraseña: ")
    try:
        bootstrap_admin(db, username, password)
        console.print(f"[green]Administrador '{username}' creado correctamente.[/green]")
        return 0
    except AuthError as error:
        console.print(f"[red]{error}[/red]")
        return 1


def cmd_register(db: AuthDB) -> int:
    console.print("[bold]Registro administrado de usuario[/bold] (requiere iniciar sesión como administrador)")
    admin_user = input("Tu usuario (administrador): ").strip()
    admin_pass = getpass.getpass("Tu contraseña: ")
    try:
        authenticate(db, admin_user, admin_pass)
    except AuthError as error:
        console.print(f"[red]No autenticado: {error}[/red]")
        return 1

    new_username = input("Usuario nuevo: ").strip()
    new_password = getpass.getpass("Contraseña nueva: ")
    console.print(f"Roles disponibles: {', '.join(ROLE_NAMES)}")
    role_name = input("Rol: ").strip()

    try:
        register_user(db, admin_user, new_username, new_password, role_name)
        console.print(f"[green]Usuario '{new_username}' creado con rol '{role_name}'.[/green]")
        return 0
    except AuthError as error:
        console.print(f"[red]{error}[/red]")
        return 1


def cmd_login(db: AuthDB) -> int:
    username = input("Usuario: ").strip()
    password = getpass.getpass("Contraseña: ")
    try:
        token = authenticate(db, username, password)
        console.print(f"[green]Login exitoso.[/green] Token de sesión: {token}")
        console.print("(en la app web, este token se guardaría en la sesión del navegador)")
        return 0
    except AuthError as error:
        console.print(f"[red]{error}[/red]")
        return 1


def cmd_check_permission(db: AuthDB) -> int:
    username = input("Usuario: ").strip()
    password = getpass.getpass("Contraseña: ")
    try:
        token = authenticate(db, username, password)
        validate_session(db, token)
    except AuthError as error:
        console.print(f"[red]{error}[/red]")
        return 1

    console.print(f"Recursos disponibles: {', '.join(RESOURCES)}")
    resource = input("Recurso a consultar: ").strip()
    try:
        level = check_permission(db, username, resource)
        console.print(f"Nivel de acceso a '{resource}': [bold]{level}[/bold]")
        return 0
    except AuthError as error:
        console.print(f"[red]{error}[/red]")
        return 1


def cmd_revoke_user(db: AuthDB) -> int:
    admin_user = input("Tu usuario (administrador): ").strip()
    admin_pass = getpass.getpass("Tu contraseña: ")
    try:
        authenticate(db, admin_user, admin_pass)
    except AuthError as error:
        console.print(f"[red]No autenticado: {error}[/red]")
        return 1

    target = input("Usuario a revocar: ").strip()
    try:
        revoke_user(db, admin_user, target)
        console.print(f"[green]Usuario '{target}' revocado.[/green]")
        return 0
    except AuthError as error:
        console.print(f"[red]{error}[/red]")
        return 1


def cmd_audit(db: AuthDB) -> int:
    table = Table(title="Últimos eventos de auditoría")
    table.add_column("Fecha")
    table.add_column("Usuario")
    table.add_column("Evento")
    table.add_column("Detalle")
    for event in get_audit_log(db, limit=30):
        table.add_row(event["timestamp"], event["username"] or "-", event["event_type"], event["detail"] or "")
    console.print(table)
    return 0


def cmd_test_authorization(db: AuthDB) -> int:
    """
    Ejercicio 9 de la actividad: pruebas de autorización.
    Verifica, sin pedir contraseñas, que la matriz de permisos se cumple
    tal como está definida en DEFAULT_PERMISSIONS.
    """
    from .auth import DEFAULT_PERMISSIONS

    console.print("[bold]Pruebas de autorización sobre la matriz de permisos[/bold]\n")
    total = 0
    passed = 0
    for role_name, resource_map in DEFAULT_PERMISSIONS.items():
        with db._conn() as conn:
            role_row = conn.execute("SELECT id FROM roles WHERE name = ?", (role_name,)).fetchone()
        for resource, expected in resource_map.items():
            with db._conn() as conn:
                row = conn.execute(
                    "SELECT allowed FROM permissions WHERE role_id = ? AND resource = ?",
                    (role_row["id"], resource),
                ).fetchone()
            actual = row["allowed"] if row else "no"
            total += 1
            ok = actual == expected
            passed += int(ok)
            status = "[green]OK[/green]" if ok else "[red]FALLO[/red]"
            console.print(f"{status} rol={role_name:<14} recurso={resource:<16} esperado={expected:<8} obtenido={actual}")

    console.print(f"\nPruebas de autorización aprobadas: {passed}/{total}")
    return 0 if passed == total else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI de autenticación y autorización")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("bootstrap-admin")
    sub.add_parser("register")
    sub.add_parser("login")
    sub.add_parser("check-permission")
    sub.add_parser("revoke-user")
    sub.add_parser("audit")
    sub.add_parser("test-authorization")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    db = AuthDB("storage/auth.db")

    commands = {
        "bootstrap-admin": cmd_bootstrap_admin,
        "register": cmd_register,
        "login": cmd_login,
        "check-permission": cmd_check_permission,
        "revoke-user": cmd_revoke_user,
        "audit": cmd_audit,
        "test-authorization": cmd_test_authorization,
    }
    return commands[args.command](db)


if __name__ == "__main__":
    sys.exit(main())
