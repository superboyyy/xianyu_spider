import asyncio
import base64
import json

from xianyu.im_client import GoofishIMClient, parse_ws_frame
from xianyu.im_protocol import (
    decode_payload,
    extract_incoming_message,
    generate_mid,
    iter_sync_packages,
    pack_msgpack,
)


TRUNCATED_SYNC = (
    "ggGLAYEBtTIyMDI2NDA5MTgwNzlAZ29vZmlzaAKzNDc4MTI4NzAwMDBAZ29vZmlzaAOxMzQwMzIwNTY4OTU4MS5QTk0EAAXPAAABlYXRFx8GggFlA4UBoAKkMTExMQOgBAEF2gA1eyJhdFVzZXJzIjpbXSwiY29udGVudFR5cGUiOjEsInRleHQiOnsidGV4dCI6IjExMTEifX0HAggBCQA"
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


def test_extract_integer_keys():
    payload = {
        1: {
            2: "888@goofish",
            10: {
                "reminderTitle": "买家小王",
                "senderUserId": "999",
                "reminderContent": "还在吗",
            },
        }
    }
    msg = extract_incoming_message(payload)
    assert msg["text"] == "还在吗"
    assert msg["conversation_id"] == "888"
    assert msg["sender_id"] == "999"


def test_extract_base64_custom_data():
    inner = {"contentType": 1, "text": {"text": "刀不刀"}}
    encoded = json.dumps(inner, separators=(",", ":"))
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


def test_msgpack_sync_package_extracts_chat():
    packed = pack_msgpack(
        {
            1: {
                2: "888@goofish",
                5: 1710000000000,
                10: {
                    "reminderTitle": "买家小王",
                    "senderUserId": "999",
                    "reminderContent": "还在吗",
                    "reminderUrl": "https://www.goofish.com/im?itemId=1",
                },
            }
        }
    )
    encoded = base64.b64encode(packed).decode("ascii")
    message = {
        "lwp": "/s/sync",
        "body": {"syncPushPackage": {"data": [{"data": encoded}]}},
    }
    packages = iter_sync_packages(message)
    msg = extract_incoming_message(packages[0])
    assert msg == {
        "conversation_id": "888",
        "sender_id": "999",
        "sender_name": "买家小王",
        "text": "还在吗",
    }


def test_truncated_msgpack_still_extracts_text():
    msg = extract_incoming_message(TRUNCATED_SYNC)
    assert msg is not None
    assert msg["text"] == "1111"
    assert "47812870000" in msg["conversation_id"] or msg["conversation_id"] == "47812870000"


def test_garbled_binary_is_not_a_chat_message():
    junk = base64.b64encode(b"\x82\x01\xff\xfe\x00").decode("ascii")
    assert extract_incoming_message(junk) is None
    assert extract_incoming_message("not-a-message") is None


def test_generate_mid_matches_web_im():
    mid = generate_mid()
    left, _, suffix = mid.rpartition(" ")
    assert suffix == "0"
    assert left.isdigit()


def test_parse_ws_binary_json_frame():
    raw = json.dumps({"lwp": "/s/sync", "headers": {"mid": "1 0"}}).encode("utf-8")
    assert parse_ws_frame(raw)["lwp"] == "/s/sync"
    assert parse_ws_frame("not-json") is None


def test_handle_sync_queues_msgpack_chat():
    packed = pack_msgpack(
        {
            1: {
                2: "77@goofish",
                10: {
                    "reminderTitle": "买家",
                    "senderUserId": "77",
                    "reminderContent": "在吗",
                },
            }
        }
    )
    encoded = base64.b64encode(packed).decode("ascii")
    client = GoofishIMClient()
    added = asyncio.run(
        client._handle_sync(
            {"lwp": "/s/sync", "body": {"syncPushPackage": {"data": [{"data": encoded}]}}}
        )
    )
    assert added == 1
    item = client._incoming.get_nowait()
    assert item["text"] == "在吗"
    assert item["conversation_id"] == "77"
