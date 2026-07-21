import re

REFUSAL_ES = (
    "No puedo compartir datos personales, información de contacto ni información "
    "que pueda exponer a Kevin o a terceras personas. Para ampliar esta información, "
    "habla directamente con Kevin a través de sus canales oficiales."
)
REFUSAL_EN = (
    "I cannot share personal data, contact information, or information that could expose "
    "Kevin or third parties. For further information, speak directly with Kevin through "
    "his official channels."
)

SENSITIVE_PATTERNS = [
    r"\b(teléfono|telefono|celular|whatsapp|correo|email|e-mail)\b",
    r"\b(dirección|direccion|domicilio|casa|vive|ubicación exacta)\b",
    r"\b(familia|esposa|esposo|hijos|padres|pareja)\b",
    r"\b(contrato|honorarios|salario|sueldo|valor del contrato)\b",
    r"\b(estudiante|alumno).*(dato|nota|cédula|cedula|correo)\b",
    r"\b(contraseña|contrasena|clave|password|token|api key)\b",
    r"\b(contact|phone|address|email|salary|family|password)\b",
]
REDACTION_PATTERNS = [
    (re.compile(r"[\w\.-]+@[\w\.-]+\.\w+", re.I), "[CORREO PROTEGIDO]"),
    (re.compile(r"(?:\+?\d[\d\s\-]{7,}\d)"), "[TELÉFONO PROTEGIDO]"),
]


def is_sensitive_query(query: str) -> bool:
    return any(re.search(pattern, query.lower(), flags=re.I) for pattern in SENSITIVE_PATTERNS)


def redact_sensitive_text(text: str) -> str:
    result = text
    for pattern, replacement in REDACTION_PATTERNS:
        result = pattern.sub(replacement, result)
    return result
