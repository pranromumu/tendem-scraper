from tendem_scraper.core import session as s


def test_session_path_sanitises(tmp_path, monkeypatch):
    monkeypatch.setattr(s, "SESSION_DIR", tmp_path)
    p = s.session_path("my login!!")
    assert p.name == "mylogin.json"
    assert p.parent == tmp_path


def test_session_exists_false_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(s, "SESSION_DIR", tmp_path)
    assert not s.session_exists("nope")


def test_list_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(s, "SESSION_DIR", tmp_path)
    (tmp_path / "a.json").write_text("{}")
    (tmp_path / "b.json").write_text("{}")
    assert s.list_sessions() == ["a", "b"]