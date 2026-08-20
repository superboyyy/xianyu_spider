import json

from xianyu.im_protocol import (
    decode_payload,
    extract_incoming_message,
    iter_sync_packages,
)


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
