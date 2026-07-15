import ariadne


def test_version_importable():
    assert isinstance(ariadne.__version__, str)
    assert ariadne.__version__
