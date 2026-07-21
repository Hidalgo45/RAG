# Fase 2: autenticación y autorización

## Objetivo

Permitir consultas únicamente a usuarios registrados y con claves autorizadas.

## Conceptos

- **Autenticación:** comprobar quién es el usuario.
- **Autorización:** decidir qué puede consultar.
- **Hash:** transformación unidireccional para almacenar contraseñas de forma segura.

Las contraseñas nunca deben guardarse en texto plano.

## Roles propuestos

- administrador;
- reclutador;
- cliente;
- estudiante;
- colega;
- usuario general autorizado.

## Requisitos

1. Registro administrado.
2. Contraseñas con Argon2 o bcrypt.
3. Base de usuarios.
4. Bloqueo temporal tras varios intentos.
5. Auditoría.
6. Matriz de permisos.
7. Expiración de sesión.
8. Revocación de usuarios.
9. Pruebas de autorización.

## Matriz inicial

| Rol | Perfil | Certificaciones | Proyectos | Datos sensibles |
|---|---:|---:|---:|---:|
| Administrador | Sí | Sí | Sí | No por defecto |
| Reclutador | Sí | Sí | Sí | No |
| Cliente | Sí | Parcial | Sí | No |
| Estudiante | Sí | Parcial | Parcial | No |
| General | Sí | Parcial | Parcial | No |

## Actividad

Diseñe una base SQLite con tablas `users`, `roles`, `permissions` y `audit_events`. Implemente autenticación por consola antes de migrar a web.
