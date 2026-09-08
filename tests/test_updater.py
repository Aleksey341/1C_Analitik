from meeting_bridge.updater import ReleaseInfo, is_newer


def test_is_newer_accepts_higher_patch():
    assert is_newer("1.1.6", "1.1.5") is True


def test_is_newer_rejects_same_version():
    assert is_newer("1.1.5", "1.1.5") is False


def test_is_newer_handles_v_prefix_and_dev_suffix():
    assert is_newer("v1.2.0", "1.1.99") is True
    assert is_newer("1.1.5", "1.1.5-dev") is False


def test_release_info_is_plain_data():
    release = ReleaseInfo(
        version="1.2.0",
        tag="v1.2.0",
        download_url="https://example.test/setup.exe",
        digest="sha256:abc",
    )
    assert release.tag == "v1.2.0"
