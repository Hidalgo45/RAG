# Ejercicios pedagógicos

## Ejercicios guiados

1. Explique la diferencia entre LLM, embedding y base vectorial.
2. Dibuje el flujo de ingestión.
3. Cambie `CHUNK_SIZE` y compare resultados.
4. Cambie `SIMILARITY_TOP_K`.
5. Agregue un PDF autorizado.
6. Modifique el tono del rol estudiante.
7. Cree cinco preguntas prohibidas.
8. Agregue metadatos de versión.
9. Compare dos modelos ligeros.
10. Mida el tiempo de diez preguntas.
11. Cree una pregunta cuya respuesta esté en dos documentos.
12. Analice una respuesta incorrecta.
13. Agregue un nuevo rol.
14. Cree una prueba para privacidad.
15. Documente un problema de chunking.

## Deber: interfaz web

Construya una interfaz web que reutilice `PersonalRAG`.

Requisitos:

- pantalla de inicio;
- selección de rol;
- campo de pregunta;
- historial;
- indicador de carga;
- mensajes de error;
- diseño adaptable;
- no mostrar rutas internas;
- no revelar fuentes salvo a administradores;
- mantener reglas de privacidad.

Opciones: Streamlit, Flask, FastAPI con HTML u otra alternativa aprobada.

## Reto avanzado

Implemente autenticación y autorización.
