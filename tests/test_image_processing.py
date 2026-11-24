from PIL import Image

from app import swap_stripes


def test_vertical_stripes_swap_and_keep_unpaired_stripe():
    image = Image.new("L", (6, 1))
    image.putdata([10, 20, 30, 40, 50, 60])

    result = swap_stripes(image, width=2, direction="vertical")

    assert list(result.getdata()) == [30, 40, 10, 20, 50, 60]


def test_horizontal_stripes_swap_rows():
    image = Image.new("L", (2, 2))
    image.putdata([10, 20, 30, 40])

    result = swap_stripes(image, width=1, direction="horizontal")

    assert list(result.getdata()) == [30, 40, 10, 20]


def test_image_is_unchanged_when_no_complete_pair_fits():
    image = Image.new("L", (3, 1))
    image.putdata([10, 20, 30])

    result = swap_stripes(image, width=2, direction="vertical")

    assert list(result.getdata()) == [10, 20, 30]
