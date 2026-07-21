from src.privacy import is_sensitive_query, redact_sensitive_text

def test_sensitive_contact_query():
    assert is_sensitive_query("¿Cuál es el correo de Kevin?")

def test_safe_profile_query():
    assert not is_sensitive_query("¿Qué certificaciones tiene Kevin?")

def test_redacts_email():
    assert "@" not in redact_sensitive_text("Escriba a persona@example.com")
