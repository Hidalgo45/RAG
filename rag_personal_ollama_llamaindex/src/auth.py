"""
Fase 2: Autenticación y autorización para el RAG personal.

Implementa:
- Base de usuarios en SQLite (users, roles, permissions, audit_events, sessions).
- Contraseñas con hash bcrypt (nunca en texto plano).
- Bloqueo temporal tras varios intentos fallidos.
- Auditoría de eventos (login exitoso/fallido, registro, revocación, etc.).
- Matriz de permisos por rol.
- Sesiones con expiración y revocación.

Este módulo es independiente de la interfaz (consola o web); ambas deben
usarlo tal cual, sin duplicar la lógica de seguridad.
"""

from __future__ import annotations

import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt

# --- Configuración de seguridad -------------------------------------------------

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
SESSION_MINUTES = 30

# Roles válidos según la guía del trabajo
ROLE_NAMES = ["administrador", "reclutador", "cliente", "estudiante", "colega", "general"]

# Recursos consultables, según la matriz de permisos de la guía
RESOURCES = ["perfil", "certificaciones", "proyectos", "datos_sensibles"]

# Matriz inicial de permisos (rol -> recurso -> nivel)
# Niveles posibles: "si" (acceso completo), "parcial", "no"
DEFAULT_PERMISSIONS = {
    "administrador": {"perfil": "si", "certificaciones": "si", "proyectos": "si", "datos_sensibles": "no"},
    "reclutador":    {"perfil": "si", "certificaciones": "si", "proyectos": "si", "datos_sensibles": "no"},
    "cliente":       {"perfil": "si", "certificaciones": "parcial", "proyectos": "si", "datos_sensibles": "no"},
    "estudiante":    {"perfil": "si", "certificaciones": "parcial", "proyectos": "parcial", "datos_sensibles": "no"},
    "colega":        {"perfil": "si", "certificaciones": "si", "proyectos": "si", "datos_sensibles": "no"},
    "general":       {"perfil": "si", "certificaciones": "parcial", "proyectos": "parcial", "datos_sensibles": "no"},
}


class AuthError(Exception):
    """Error de autenticación o autorización, con un motivo legible."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse(dt_str: str | None) -> datetime | None:
    if not dt_str:
        return None
    return datetime.fromisoformat(dt_str)


# --- Conexión y esquema ---------------------------------------------------------

class AuthDB:
    def __init__(self, db_path: str | Path = "storage/auth.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                );

                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role_id INTEGER NOT NULL REFERENCES roles(id),
                    active INTEGER NOT NULL DEFAULT 1,
                    failed_attempts INTEGER NOT NULL DEFAULT 0,
                    locked_until TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role_id INTEGER NOT NULL REFERENCES roles(id),
                    resource TEXT NOT NULL,
                    allowed TEXT NOT NULL CHECK (allowed IN ('si', 'parcial', 'no')),
                    UNIQUE(role_id, resource)
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    event_type TEXT NOT NULL,
                    detail TEXT,
                    timestamp TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked INTEGER NOT NULL DEFAULT 0
                );
                """
            )
            self._seed_roles_and_permissions(conn)

    def _seed_roles_and_permissions(self, conn: sqlite3.Connection) -> None:
        for role_name in ROLE_NAMES:
            conn.execute("INSERT OR IGNORE INTO roles (name) VALUES (?)", (role_name,))

        role_ids = {row["name"]: row["id"] for row in conn.execute("SELECT id, name FROM roles")}
        for role_name, resource_map in DEFAULT_PERMISSIONS.items():
            role_id = role_ids[role_name]
            for resource, allowed in resource_map.items():
                conn.execute(
                    "INSERT OR IGNORE INTO permissions (role_id, resource, allowed) VALUES (?, ?, ?)",
                    (role_id, resource, allowed),
                )


# --- Auditoría --------------------------------------------------------------------

def log_audit(db: AuthDB, username: str | None, event_type: str, detail: str = "") -> None:
    with db._conn() as conn:
        conn.execute(
            "INSERT INTO audit_events (username, event_type, detail, timestamp) VALUES (?, ?, ?, ?)",
            (username, event_type, detail, _iso(_now())),
        )


def get_audit_log(db: AuthDB, limit: int = 50) -> list[sqlite3.Row]:
    with db._conn() as conn:
        return conn.execute(
            "SELECT * FROM audit_events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()


# --- Gestión de usuarios (registro administrado) ----------------------------------

def register_user(db: AuthDB, actor_username: str | None, username: str, password: str, role_name: str) -> None:
    """
    Registra un nuevo usuario. El registro es 'administrado': solo un
    administrador (o el bootstrap inicial, actor_username=None) puede crear cuentas.
    """
    if role_name not in ROLE_NAMES:
        raise AuthError(f"Rol inválido: {role_name}")

    if actor_username is not None:
        actor_role = get_user_role(db, actor_username)
        if actor_role != "administrador":
            log_audit(db, actor_username, "registro_denegado", f"intento de crear '{username}' sin permisos")
            raise AuthError("Solo un administrador puede registrar nuevos usuarios.")

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    with db._conn() as conn:
        role_row = conn.execute("SELECT id FROM roles WHERE name = ?", (role_name,)).fetchone()
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash, role_id, active, created_at) "
                "VALUES (?, ?, ?, 1, ?)",
                (username, password_hash, role_row["id"], _iso(_now())),
            )
        except sqlite3.IntegrityError as exc:
            raise AuthError(f"El usuario '{username}' ya existe.") from exc

    log_audit(db, actor_username, "registro_usuario", f"usuario creado: {username} (rol={role_name})")


def get_user_role(db: AuthDB, username: str) -> str | None:
    with db._conn() as conn:
        row = conn.execute(
            "SELECT roles.name AS role_name FROM users "
            "JOIN roles ON roles.id = users.role_id WHERE users.username = ?",
            (username,),
        ).fetchone()
    return row["role_name"] if row else None


def revoke_user(db: AuthDB, actor_username: str, username: str) -> None:
    actor_role = get_user_role(db, actor_username)
    if actor_role != "administrador":
        raise AuthError("Solo un administrador puede revocar usuarios.")

    with db._conn() as conn:
        conn.execute("UPDATE users SET active = 0 WHERE username = ?", (username,))
    with db._conn() as conn:
        conn.execute(
            "UPDATE sessions SET revoked = 1 WHERE username = ?", (username,)
        )
    log_audit(db, actor_username, "revocacion_usuario", f"usuario revocado: {username}")


# --- Autenticación (login con bloqueo temporal) -----------------------------------

def authenticate(db: AuthDB, username: str, password: str) -> str:
    """
    Verifica usuario y contraseña. Si es correcto, crea una sesión y
    devuelve el token. Lanza AuthError con un mensaje claro en caso contrario.
    Aplica bloqueo temporal tras MAX_FAILED_ATTEMPTS intentos fallidos.
    """
    with db._conn() as conn:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

    if user is None:
        log_audit(db, username, "login_fallido", "usuario no existe")
        raise AuthError("Usuario o contraseña incorrectos.")

    if not user["active"]:
        log_audit(db, username, "login_rechazado", "usuario revocado/inactivo")
        raise AuthError("Esta cuenta ha sido revocada.")

    locked_until = _parse(user["locked_until"])
    if locked_until and _now() < locked_until:
        minutos_restantes = int((locked_until - _now()).total_seconds() // 60) + 1
        log_audit(db, username, "login_bloqueado", f"cuenta bloqueada, faltan ~{minutos_restantes} min")
        raise AuthError(f"Cuenta bloqueada temporalmente. Intenta de nuevo en {minutos_restantes} min.")

    password_ok = bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8"))

    if not password_ok:
        _register_failed_attempt(db, user)
        raise AuthError("Usuario o contraseña incorrectos.")

    # Login correcto: reiniciar contador de intentos fallidos
    with db._conn() as conn:
        conn.execute(
            "UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE username = ?",
            (username,),
        )
    log_audit(db, username, "login_exitoso")

    return _create_session(db, username)


def _register_failed_attempt(db: AuthDB, user: sqlite3.Row) -> None:
    username = user["username"]
    new_attempts = user["failed_attempts"] + 1

    locked_until_value = None
    if new_attempts >= MAX_FAILED_ATTEMPTS:
        locked_until_value = _iso(_now() + timedelta(minutes=LOCKOUT_MINUTES))
        log_audit(db, username, "cuenta_bloqueada", f"tras {new_attempts} intentos fallidos")

    with db._conn() as conn:
        conn.execute(
            "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE username = ?",
            (new_attempts, locked_until_value, username),
        )

    log_audit(db, username, "login_fallido", f"intento {new_attempts}/{MAX_FAILED_ATTEMPTS}")


# --- Sesiones (expiración y revocación) --------------------------------------------

def _create_session(db: AuthDB, username: str) -> str:
    token = secrets.token_urlsafe(32)
    created = _now()
    expires = created + timedelta(minutes=SESSION_MINUTES)
    with db._conn() as conn:
        conn.execute(
            "INSERT INTO sessions (token, username, created_at, expires_at, revoked) "
            "VALUES (?, ?, ?, ?, 0)",
            (token, username, _iso(created), _iso(expires)),
        )
    return token


def validate_session(db: AuthDB, token: str) -> str:
    """Devuelve el username si la sesión es válida; lanza AuthError si no."""
    with db._conn() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE token = ?", (token,)).fetchone()

    if row is None or row["revoked"]:
        raise AuthError("Sesión inválida o cerrada.")

    if _now() > _parse(row["expires_at"]):
        raise AuthError("La sesión ha expirado. Vuelve a iniciar sesión.")

    return row["username"]


def logout(db: AuthDB, token: str) -> None:
    with db._conn() as conn:
        conn.execute("UPDATE sessions SET revoked = 1 WHERE token = ?", (token,))


# --- Autorización (matriz de permisos) ----------------------------------------------

def check_permission(db: AuthDB, username: str, resource: str) -> str:
    """Devuelve el nivel de acceso ('si' | 'parcial' | 'no') del usuario a un recurso."""
    if resource not in RESOURCES:
        raise AuthError(f"Recurso desconocido: {resource}")

    role_name = get_user_role(db, username)
    if role_name is None:
        raise AuthError("Usuario no encontrado.")

    with db._conn() as conn:
        row = conn.execute(
            "SELECT permissions.allowed FROM permissions "
            "JOIN roles ON roles.id = permissions.role_id "
            "WHERE roles.name = ? AND permissions.resource = ?",
            (role_name, resource),
        ).fetchone()

    level = row["allowed"] if row else "no"
    log_audit(db, username, "verificacion_permiso", f"recurso={resource} nivel={level}")
    return level


def bootstrap_admin(db: AuthDB, username: str, password: str) -> None:
    """Crea el primer administrador si todavía no existe ninguno. Solo debe usarse una vez."""
    with db._conn() as conn:
        existing_admin = conn.execute(
            "SELECT users.id FROM users JOIN roles ON roles.id = users.role_id "
            "WHERE roles.name = 'administrador' LIMIT 1"
        ).fetchone()
    if existing_admin:
        raise AuthError("Ya existe al menos un administrador; use 'register' autenticado como admin.")
    register_user(db, actor_username=None, username=username, password=password, role_name="administrador")
