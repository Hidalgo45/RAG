"""
Interfaz web para el RAG personal (Ollama + LlamaIndex + Qdrant).

Ejecutar con:
    streamlit run app.py
"""

import os
import time

import streamlit as st

from src.config import AppConfig
from src.rag import PersonalRAG
from src.roles import ROLES

st.set_page_config(
    page_title="RAG Personal",
    page_icon="🤖",
    layout="centered",
)

# Contraseña de administrador: definila en tu .env como ADMIN_PASSWORD=algo-secreto
# Si no se define, el modo administrador queda deshabilitado por defecto.
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")


@st.cache_resource(show_spinner="Cargando modelo e indice vectorial...")
def load_rag():
    """Crea una sola instancia de PersonalRAG y la reutiliza entre recargas."""
    config = AppConfig()
    return PersonalRAG(config)


def init_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "role_key" not in st.session_state:
        st.session_state.role_key = "5"  # Publico general por defecto
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False


def render_sidebar():
    """Dibuja el panel lateral con selector de rol y opciones.
    Devuelve (role_key, show_sources)."""
    with st.sidebar:
        st.header("Configuración")

        role_labels = {key: value["label"] for key, value in ROLES.items()}
        selected_key = st.radio(
            "¿Quién realiza la consulta?",
            options=list(role_labels.keys()),
            format_func=lambda k: role_labels[k],
            index=list(role_labels.keys()).index(st.session_state.role_key),
        )
        st.session_state.role_key = selected_key

        st.divider()

        # --- Modo administrador: las fuentes solo se muestran si se autentica ---
        st.subheader("Modo administrador")
        if not st.session_state.is_admin:
            with st.form("admin_login", clear_on_submit=True):
                pwd = st.text_input("Contraseña", type="password")
                submitted = st.form_submit_button("Ingresar")
                if submitted:
                    if ADMIN_PASSWORD and pwd == ADMIN_PASSWORD:
                        st.session_state.is_admin = True
                        st.rerun()
                    else:
                        st.error("Contraseña incorrecta.")
        else:
            st.success("Sesión de administrador activa.")
            if st.button("Cerrar sesión de administrador", use_container_width=True):
                st.session_state.is_admin = False
                st.rerun()

        show_sources = st.session_state.is_admin and st.toggle(
            "Mostrar fuentes", value=True, disabled=not st.session_state.is_admin
        )
        if not st.session_state.is_admin:
            st.caption("Las fuentes solo son visibles para administradores.")

        st.divider()
        if st.button("Limpiar conversación", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

        st.caption(
            "Este asistente responde solo con base en los documentos autorizados "
            "que fueron indexados previamente. Los datos sensibles se filtran "
            "automáticamente antes de mostrarse."
        )

    return selected_key, show_sources


def render_sources(sources) -> None:
    with st.expander("Ver fuentes"):
        for source in sources:
            st.markdown(
                f"**{source['file_name']}** &nbsp;|&nbsp; score={source['score']:.4f}\n\n"
                f"> {source['text']}"
            )


def render_history(show_sources: bool) -> None:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant" and show_sources and message.get("sources"):
                render_sources(message["sources"])


def main() -> None:
    init_session_state()

    st.title("🤖 RAG Personal")
    st.caption("Consulta mis documentos (CV, certificados) usando un modelo local vía Ollama.")

    role_key, show_sources = render_sidebar()
    role = ROLES[role_key]

    # --- Carga del sistema con manejo de errores (sin exponer rutas ni tracebacks) ---
    try:
        rag = load_rag()
    except Exception:
        st.error(
            "No se pudo iniciar el asistente. Verifica que Ollama esté corriendo "
            "y que los documentos hayan sido ingestados (`python -m src.cli ingest`)."
        )
        st.stop()

    render_history(show_sources)

    query = st.chat_input("Escribe tu pregunta...")
    if query:
        st.session_state.messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query)

        with st.chat_message("assistant"):
            try:
                with st.spinner("Pensando..."):
                    start = time.perf_counter()
                    result = rag.ask(query, role)
                    elapsed = time.perf_counter() - start
            except Exception:
                # Mensaje de error genérico: nunca mostrar la excepción cruda
                # (podría contener rutas internas o detalles técnicos).
                error_answer = (
                    "Ocurrió un problema al generar la respuesta. Intenta de nuevo "
                    "en unos segundos; si persiste, revisa que Ollama siga activo."
                )
                st.error(error_answer)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_answer, "sources": []}
                )
                st.stop()

            st.markdown(result["answer"])
            st.caption(f"Tiempo de respuesta: {elapsed:.2f}s | Rol: {role['label']}")

            if show_sources and result["sources"]:
                render_sources(result["sources"])

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": result["answer"],
                "sources": result["sources"],
            }
        )


if __name__ == "__main__":
    main()
