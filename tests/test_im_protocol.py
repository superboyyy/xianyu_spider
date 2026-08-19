import json

from im_protocol import (
    decode_payload,
    dump_cookie_header,
    extract_incoming_message,
    is_system_sender,
    iter_sync_packages,
    match_auto_reply,
    parse_cookie_header,
    render_reply,
)


def test_parse_and_dump_cookie_header():
    parsed = parse_cookie_header("unb=10001; cookie2=abc;  _m_h5_tk=tok_1")
    assert parsed["unb"] == "10001"
    assert parsed["cookie2"] == "abc"
    assert parsed["_m_h5_tk"] == "tok_1"
    dumped = dump_cookie_header(parsed)
    assert "unb=10001" in dumped
    assert parse_cookie_header("") == {}


def test_extract_numbered_sync_message():
    payload = {
        "1": {
            "2": "888@goofish",
            "10": {
                "reminderTitle": "买家小王",
                "senderUserId": "999",
                "reminderContent": "还在吗",
            },
        }
    }
    msg = extract_incoming_message(payload)
    assert msg == {
        "conversation_id": "888",
        "sender_id": "999",
        "sender_name": "买家小王",
        "text": "还在吗",
    }


def test_extract_base64_custom_data():
    inner = {"contentType": 1, "text": {"text": "刀不刀"}}
    encoded = json.dumps(inner, separators=(",", ":"))
    import base64

    payload = {"custom": {"data": base64.b64encode(encoded.encode()).decode()}}
    msg = extract_incoming_message(payload)
    assert msg["text"] == "刀不刀"


def test_iter_sync_packages_and_json_string():
    message = {
        "lwp": "/s/sync",
        "body": {
            "syncPushPackage": {
                "data": [{"data": json.dumps({"reminderContent": "你好", "cid": "1"})}]
            }
        },
    }
    packages = iter_sync_packages(message)
    assert len(packages) == 1
    decoded = decode_payload(packages[0])
    extracted = extract_incoming_message(decoded)
    assert extracted["text"] == "你好"


def test_match_auto_reply_keyword_and_default():
    rules = [{"keyword": "在吗", "reply": "在的，亲"}, {"keyword": "刀", "reply": "可小刀"}]
    assert match_auto_reply("老板还在吗", "默认回复", rules) == "在的，亲"
    assert match_auto_reply("能刀吗", "默认回复", rules) == "可小刀"
    assert match_auto_reply("这个多少钱", "默认回复", rules) == "默认回复"
    assert match_auto_reply("   ", "默认回复", rules) is None


def test_render_reply_placeholders():
    text = render_reply("你好{sender_name}，收到：{text}", {"sender_name": "阿强", "text": "还在吗"})
    assert text == "你好阿强，收到：还在吗"


def test_system_sender_skipped():
    assert is_system_sender("闲小蜜", "hello") is True
    assert is_system_sender("买家", "还在吗") is False
