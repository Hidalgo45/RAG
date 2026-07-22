ROLES = {
    "1": {"key": "reclutador", "label": "Reclutador",
          "style": "formal, preciso, verificable y orientado a competencias y resultados"},
    "2": {"key": "cliente", "label": "Cliente potencial",
          "style": "comercial, claro, consultivo y orientado al valor"},
    "3": {"key": "estudiante", "label": "Estudiante",
      "style": "cercano y motivador, explica con analogías sencillas, "
               "evita jerga técnica sin explicarla primero, y anima a seguir aprendiendo"},
    "4": {"key": "colega", "label": "Colega profesional",
          "style": "técnico, directo, colaborativo y profesional"},
    "5": {"key": "general", "label": "Público general",
          "style": "cercano, profesional y fácil de entender"},
"6": {"key": "entrevistador", "label": "Entrevistador técnico",
            "style": "riguroso, orientado a validar experiencia real y profundidad técnica"}, 
}


def menu_roles() -> str:
    return "\n".join(f"{key}. {value['label']}" for key, value in ROLES.items())


def get_role(selection: str) -> dict:
    return ROLES.get(selection.strip(), ROLES["5"])
