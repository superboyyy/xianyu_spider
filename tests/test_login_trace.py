from xianyu.login_trace import append_event, format_trace_line, mask_secret, redact_url, summarize_passport


def test_redact_url_keeps_keys_not_values():
    url = "https://passport.goofish.com/iv/verify.htm?token=super-secret&from=qr"
    text = redact_url(url)
    assert "passport.goofish.com/iv/verify.htm" in text
    assert "token" in text
    assert "super-secret" not in text


def test_mask_secret_does_not_dump_full_token():
    assert "abcdef" not in mask_secret("abcdefghijklmn")
    assert "len14" in mask_secret("abcdefghijklmn")


def test_summarize_passport_and_append_event(tmp_path, monkeypatch):
    import xianyu.login_trace as login_trace

    monkeypatch.setattr(login_trace, "TRACE_PATH", tmp_path / "login_trace.jsonl")
    session = {"login_token": "secret-token"}
    summary = summarize_passport(
        {
            "qrCodeStatus": "CONFIRMED",
            "token": "secret-token",
            "iframeRedirectUrl": "https://passport.goofish.com/iv/verify.htm?token=abc",
            "title": "need verify",
        }
    )
    assert summary["has_token"] is True
    assert "secret-token" not in str(summary)
    record = append_event("sess1", "exchange_attempt", session, path="/login_token/login.do", new_cookies=[])
    assert record["event"] == "exchange_attempt"
    assert "secret-token" not in format_trace_line(record)
    events = login_trace.recent_events("sess1")
    assert len(events) == 1
