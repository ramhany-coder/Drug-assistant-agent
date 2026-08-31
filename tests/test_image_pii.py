import base64

from agents.image_pii.image_pii import _decode_data_uri, image_pii, settings


def test_decode_data_uri_roundtrips_valid_payload():
    payload = base64.b64encode(b"fake-image-bytes").decode("utf-8")
    assert _decode_data_uri(f"data:image/jpeg;base64,{payload}") == b"fake-image-bytes"


def test_decode_data_uri_rejects_plain_url():
    assert _decode_data_uri("https://example.com/photo.jpg") is None


def test_decode_data_uri_rejects_malformed_base64():
    assert _decode_data_uri("data:image/jpeg;base64,not-valid-base64!!!") is None


def test_no_image_short_circuits_without_touching_the_engine():
    assert image_pii({}) == {"image_cleaned": None, "image_redaction_mode": "no_image"}


def test_disabled_passes_the_image_through_unredacted(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_IMAGE_PII", False)
    image = "data:image/jpeg;base64,AAAA"
    assert image_pii({"image": image}) == {
        "image_cleaned": image,
        "image_redaction_mode": "disabled",
    }


def test_unsupported_source_is_blocked_not_fetched():
    # A plain URL is never downloaded server-side (SSRF risk) -- it must be
    # blocked closed, same as any other redaction failure.
    result = image_pii({"image": "https://example.com/photo.jpg"})
    assert result == {"image_cleaned": None, "image_redaction_mode": "blocked_unsupported_source"}
