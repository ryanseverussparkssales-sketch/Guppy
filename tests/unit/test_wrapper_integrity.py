from tools import check_wrapper_integrity


def test_wrapper_integrity_passes() -> None:
    assert check_wrapper_integrity.main() == 0
