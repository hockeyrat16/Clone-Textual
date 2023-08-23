import pytest

from textual.app import App, ComposeResult
from textual.document import Document, Selection
from textual.geometry import Offset
from textual.widgets import TextArea

TEXT = """I must not fear.
Fear is the mind-killer.
Fear is the little-death that brings total obliteration.
I will face my fear.
"""


class TextAreaApp(App):
    def compose(self) -> ComposeResult:
        text_area = TextArea()
        text_area.load_text(TEXT)
        yield text_area


def test_default_selection():
    """The cursor starts at (0, 0) in the document."""
    text_area = TextArea()
    assert text_area.selection == Selection.cursor((0, 0))


async def test_cursor_location_get():
    app = TextAreaApp()
    async with app.run_test():
        text_area = app.query_one(TextArea)
        text_area.selection = Selection((1, 1), (2, 2))
        assert text_area.cursor_location == (2, 2)


async def test_cursor_location_set():
    app = TextAreaApp()
    async with app.run_test():
        text_area = app.query_one(TextArea)
        text_area.selection = Selection((1, 1), (2, 2))
        text_area.move_cursor((2, 3), select=True)
        assert text_area.selection == Selection((1, 1), (2, 3))


async def test_selected_text_forward():
    """Selecting text from top to bottom results in the correct selected_text."""
    app = TextAreaApp()
    async with app.run_test():
        text_area = app.query_one(TextArea)
        text_area.selection = Selection((0, 0), (2, 0))
        assert (
            text_area.selected_text
            == """\
I must not fear.
Fear is the mind-killer.
"""
        )


async def test_selected_text_backward():
    """Selecting text from bottom to top results in the correct selected_text."""
    app = TextAreaApp()
    async with app.run_test():
        text_area = app.query_one(TextArea)
        text_area.selection = Selection((2, 0), (0, 0))
        assert (
            text_area.selected_text
            == """\
I must not fear.
Fear is the mind-killer.
"""
        )


async def test_selected_text_multibyte():
    app = TextAreaApp()
    async with app.run_test():
        text_area = app.query_one(TextArea)
        text_area.load_text("こんにちは")
        text_area.selection = Selection((0, 1), (0, 3))
        assert text_area.selected_text == "んに"


async def test_selection_clamp():
    """When you set the selection reactive, it's clamped to within the document bounds."""
    app = TextAreaApp()
    async with app.run_test():
        text_area = app.query_one(TextArea)
        text_area.selection = Selection((99, 99), (100, 100))
        assert text_area.selection == Selection(start=(4, 0), end=(4, 0))


async def test_mouse_click():
    """When you click the TextArea, the cursor moves to the expected location."""
    app = TextAreaApp()
    async with app.run_test() as pilot:
        text_area = app.query_one(TextArea)
        await pilot.click(TextArea, Offset(x=5, y=2))
        assert text_area.selection == Selection.cursor((2, 2))


async def test_mouse_click_clamp_from_right():
    """When you click to the right of the document bounds, the cursor is clamped
    to within the document bounds."""
    app = TextAreaApp()
    async with app.run_test() as pilot:
        text_area = app.query_one(TextArea)
        await pilot.click(TextArea, Offset(x=8, y=20))
        assert text_area.selection == Selection.cursor((4, 0))


async def test_mouse_click_gutter_clamp():
    """When you click the gutter, it selects the start of the line."""
    app = TextAreaApp()
    async with app.run_test() as pilot:
        text_area = app.query_one(TextArea)
        await pilot.click(TextArea, Offset(x=0, y=3))
        assert text_area.selection == Selection.cursor((3, 0))


async def test_cursor_selection_right():
    """When you press shift+right the selection is updated correctly."""
    app = TextAreaApp()
    async with app.run_test() as pilot:
        text_area = app.query_one(TextArea)
        await pilot.press(*["shift+right"] * 3)
        assert text_area.selection == Selection((0, 0), (0, 3))


async def test_cursor_selection_right_to_previous_line():
    """When you press shift+right resulting in the cursor moving to the next line,
    the selection is updated correctly."""
    app = TextAreaApp()
    async with app.run_test() as pilot:
        text_area = app.query_one(TextArea)
        text_area.selection = Selection.cursor((0, 15))
        await pilot.press(*["shift+right"] * 4)
        assert text_area.selection == Selection((0, 15), (1, 2))


async def test_cursor_selection_left():
    """When you press shift+left the selection is updated correctly."""
    app = TextAreaApp()
    async with app.run_test() as pilot:
        text_area = app.query_one(TextArea)
        text_area.selection = Selection.cursor((2, 5))
        await pilot.press(*["shift+left"] * 3)
        assert text_area.selection == Selection((2, 5), (2, 2))


async def test_cursor_selection_left_to_previous_line():
    """When you press shift+left resulting in the cursor moving back to the previous line,
    the selection is updated correctly."""
    app = TextAreaApp()
    async with app.run_test() as pilot:
        text_area = app.query_one(TextArea)
        text_area.selection = Selection.cursor((2, 2))
        await pilot.press(*["shift+left"] * 3)

        # The cursor jumps up to the end of the line above.
        end_of_previous_line = len(TEXT.splitlines()[1])
        assert text_area.selection == Selection((2, 2), (1, end_of_previous_line))


async def test_cursor_selection_up():
    """When you press shift+up the selection is updated correctly."""
    app = TextAreaApp()
    async with app.run_test() as pilot:
        text_area = app.query_one(TextArea)
        text_area.move_cursor((2, 3))

        await pilot.press("shift+up")
        assert text_area.selection == Selection((2, 3), (1, 3))


async def test_cursor_selection_up_when_cursor_on_first_line():
    """When you press shift+up the on the first line, it selects to the start."""
    app = TextAreaApp()
    async with app.run_test() as pilot:
        text_area = app.query_one(TextArea)
        text_area.move_cursor((0, 4))

        await pilot.press("shift+up")
        assert text_area.selection == Selection((0, 4), (0, 0))
        await pilot.press("shift+up")
        assert text_area.selection == Selection((0, 4), (0, 0))


async def test_cursor_selection_down():
    app = TextAreaApp()
    async with app.run_test() as pilot:
        text_area = app.query_one(TextArea)
        text_area.move_cursor((2, 5))

        await pilot.press("shift+down")
        assert text_area.selection == Selection((2, 5), (3, 5))


async def test_cursor_selection_down_when_cursor_on_last_line():
    app = TextAreaApp()
    async with app.run_test() as pilot:
        text_area = app.query_one(TextArea)
        text_area.load_text("ABCDEF\nGHIJK")
        text_area.move_cursor((1, 2))

        await pilot.press("shift+down")
        assert text_area.selection == Selection((1, 2), (1, 5))
        await pilot.press("shift+down")
        assert text_area.selection == Selection((1, 2), (1, 5))


@pytest.mark.parametrize("key", ["end", "ctrl+e"])
async def test_cursor_to_line_end(key):
    """You can use the keyboard to jump the cursor to the end of the current line."""
    app = TextAreaApp()
    async with app.run_test() as pilot:
        text_area = app.query_one(TextArea)
        text_area.selection = Selection.cursor((2, 2))
        await pilot.press(key)
        eol_index = len(TEXT.splitlines()[2])
        assert text_area.cursor_location == (2, eol_index)
        assert text_area.selection.is_empty


@pytest.mark.parametrize("key", ["home", "ctrl+a"])
async def test_cursor_to_line_home(key):
    """You can use the keyboard to jump the cursor to the start of the current line."""
    app = TextAreaApp()
    async with app.run_test() as pilot:
        text_area = app.query_one(TextArea)
        text_area.selection = Selection.cursor((2, 2))
        await pilot.press(key)
        assert text_area.cursor_location == (2, 0)
        assert text_area.selection.is_empty


@pytest.mark.parametrize(
    "start,end",
    [
        ((0, 0), (0, 0)),
        ((0, 4), (0, 3)),
        ((1, 0), (0, 16)),
    ],
)
async def test_get_cursor_left_location(start, end):
    app = TextAreaApp()
    async with app.run_test():
        text_area = app.query_one(TextArea)
        text_area.move_cursor(start)
        assert text_area.get_cursor_left_location() == end


@pytest.mark.parametrize(
    "start,end",
    [
        ((0, 0), (0, 1)),
        ((0, 16), (1, 0)),
        ((3, 20), (4, 0)),
    ],
)
async def test_get_cursor_right_location(start, end):
    app = TextAreaApp()
    async with app.run_test():
        text_area = app.query_one(TextArea)
        text_area.move_cursor(start)
        assert text_area.get_cursor_right_location() == end


@pytest.mark.parametrize(
    "start,end",
    [
        ((0, 4), (0, 0)),  # jump to start
        ((1, 2), (0, 2)),  # go to column above
        ((2, 56), (1, 24)),  # snap to end of row above
    ],
)
async def test_get_cursor_up_location(start, end):
    app = TextAreaApp()
    async with app.run_test():
        text_area = app.query_one(TextArea)
        text_area.move_cursor(start)
        # This is required otherwise the cursor will snap back to the
        # last location navigated to (0, 0)
        text_area.record_cursor_width()
        assert text_area.get_cursor_up_location() == end


@pytest.mark.parametrize(
    "start,end",
    [
        ((3, 4), (4, 0)),  # jump to end
        ((1, 2), (2, 2)),  # go to column above
        ((2, 56), (3, 20)),  # snap to end of row below
    ],
)
async def test_get_cursor_down_location(start, end):
    app = TextAreaApp()
    async with app.run_test():
        text_area = app.query_one(TextArea)
        text_area.move_cursor(start)
        # This is required otherwise the cursor will snap back to the
        # last location navigated to (0, 0)
        text_area.record_cursor_width()
        assert text_area.get_cursor_down_location() == end


async def test_cursor_page_down():
    """Pagedown moves the cursor down 1 page, retaining column index."""
    app = TextAreaApp()
    async with app.run_test() as pilot:
        text_area = app.query_one(TextArea)
        text_area.load_text("XXX\n" * 200)
        text_area.selection = Selection.cursor((0, 1))
        await pilot.press("pagedown")
        assert text_area.selection == Selection.cursor((app.console.height - 1, 1))


async def test_cursor_page_up():
    """Pageup moves the cursor up 1 page, retaining column index."""
    app = TextAreaApp()
    async with app.run_test() as pilot:
        text_area = app.query_one(TextArea)
        text_area.load_text("XXX\n" * 200)
        text_area.selection = Selection.cursor((100, 1))
        await pilot.press("pageup")
        assert text_area.selection == Selection.cursor(
            (100 - app.console.height + 1, 1)
        )


async def test_cursor_vertical_movement_visual_alignment_snapping():
    """When you move the cursor vertically, it should stay vertically
    aligned even when double-width characters are used."""
    app = TextAreaApp()
    async with app.run_test() as pilot:
        text_area = app.query_one(TextArea)
        text_area.load_document(Document("こんにちは\n012345"))
        text_area.move_cursor((1, 3), record_width=True)

        # The '3' is aligned with ん at (0, 1)
        # こんにちは
        # 012345
        # Pressing `up` takes us from (1, 3) to (0, 1) because record_width=True.
        await pilot.press("up")
        assert text_area.selection == Selection.cursor((0, 1))

        # Pressing `down` takes us from (0, 1) to (1, 3)
        await pilot.press("down")
        assert text_area.selection == Selection.cursor((1, 3))


@pytest.mark.parametrize(
    "content,expected_selection",
    [
        ("123\n456\n789", Selection((0, 0), (2, 3))),
        ("123\n456\n789\n", Selection((0, 0), (3, 0))),
        ("", Selection((0, 0), (0, 0))),
    ],
)
async def test_select_all(content, expected_selection):
    app = TextAreaApp()
    async with app.run_test():
        text_area = app.query_one(TextArea)
        text_area.load_text(content)

        text_area.select_all()

        assert text_area.selection == expected_selection


@pytest.mark.parametrize(
    "index,content,expected_selection",
    [
        (1, "123\n456\n789\n", Selection((1, 0), (1, 3))),
        (2, "123\n456\n789\n", Selection((2, 0), (2, 3))),
        (3, "123\n456\n789\n", Selection((3, 0), (3, 0))),
        (0, "", Selection((0, 0), (0, 0))),
    ],
)
async def test_select_line(index, content, expected_selection):
    app = TextAreaApp()
    async with app.run_test():
        text_area = app.query_one(TextArea)
        text_area.load_text(content)

        text_area.select_line(index)

        assert text_area.selection == expected_selection