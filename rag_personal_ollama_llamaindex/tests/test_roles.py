from src.roles import get_role

def test_default_role():
    assert get_role("99")["key"] == "general"

def test_recruiter_role():
    assert get_role("1")["key"] == "reclutador"
