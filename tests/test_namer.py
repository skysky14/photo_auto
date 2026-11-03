from photo_ai import namer


def test_sanitize_removes_invalid_and_spaces():
    assert namer.sanitize('해변: 일몰?/ 사진.') == "해변_일몰_사진"


def test_build_name_with_and_without_date():
    assert namer.build_name("해변 일몰", "2024-05-01", ".JPG") == "2024-05-01_해변_일몰.jpg"
    assert namer.build_name("해변 일몰", None, ".png") == "해변_일몰.png"


def test_unique_path(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"")
    assert namer.unique_path(tmp_path / "a.jpg").name == "a_2.jpg"
    assert namer.unique_path(tmp_path / "a.jpg", {tmp_path / "a_2.jpg"}).name == "a_3.jpg"
