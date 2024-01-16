from __future__ import annotations

import re
from typing import Iterable

from rich.cells import chop_cells

from ._cells import cell_len
from ._loop import loop_last
from .expand_tabs import get_tab_widths

re_chunk = re.compile(r"\s*\S+\s*")


def chunks(text: str) -> Iterable[tuple[int, int, str]]:
    """Yields each "chunk" from the text as a tuple containing (start_index, end_index, chunk_content).
    A "chunk" in this context refers to a word and any whitespace around it.

    Args:
        text: The text to split into chunks.

    Returns:
        Yields tuples containing the start, end and content for each chunk.
    """
    end = 0
    while (chunk_match := re_chunk.match(text, end)) is not None:
        start, end = chunk_match.span()
        chunk = chunk_match.group(0)
        yield start, end, chunk


def divide_line(
    text: str,
    width: int,
    tab_size: int,
    fold: bool = True,
) -> list[int]:
    """Given a string of text, and a width (measured in cells), return a list
    of codepoint indices which the string should be split at in order for it to fit
    within the given width.

    Args:
        text: The text to examine.
        width: The available cell width.
        tab_size: The tab stop width.
        fold: If True, words longer than `width` will be folded onto a new line.

    Returns:
        A list of indices to break the line at.
    """
    break_positions: list[int] = []  # offsets to insert the breaks at
    append = break_positions.append
    cell_offset = 0
    _cell_len = cell_len

    # todo! could we offset the wrap offsets after computing them, by going through them, and summing the widths of
    #  all tab characters that appeared before the wrap offset on the line? for example if we have a wrap offset of
    #  14, then we go through the tab_widths tuples until we’ve seen 14 codepoints, and note the total widths of tabs
    #  encountered.

    # build mapping of tab positions to tab widths. then, for each chunk, check if a
    # get all of the tab

    # foo\tbar\t\baz

    tab_widths = get_tab_widths(text, tab_size)
    cumulative_widths = []
    cumulative_width = 0
    for tab_section, tab_width in tab_widths:
        cumulative_widths.extend([cumulative_width] * len(tab_section))
        cumulative_width += tab_width

    for start, end, chunk in chunks(text):
        # todo, 1st, terrible name, 2nd can we get the "word width" here to account
        #  for tab widths?
        chunk_width = _cell_len(chunk)
        print(start, end, chunk, len(chunk))
        tab_width_before_start = cumulative_widths[start]
        tab_width_before_end = cumulative_widths[end]
        chunk_tab_width = tab_width_before_end - tab_width_before_start
        chunk_width += chunk_tab_width
        remaining_space = width - cell_offset
        chunk_fits = remaining_space >= chunk_width

        if chunk_fits:
            # Simplest case - the word fits within the remaining width for this line.
            cell_offset += chunk_width
        else:
            # Not enough space remaining for this word on the current line.
            if chunk_width > width:
                # The word doesn't fit on any line, so we can't simply
                # place it on the next line...
                if fold:
                    # Fold the word across multiple lines.
                    folded_word = chop_cells(chunk, width=width)
                    for last, line in loop_last(folded_word):
                        if start:
                            append(start)
                        if last:
                            cell_offset = _cell_len(line)
                        else:
                            start += len(line)
                else:
                    # Folding isn't allowed, so crop the word.
                    if start:
                        append(start)
                    cell_offset = chunk_width
            elif cell_offset and start:
                # The word doesn't fit within the remaining space on the current
                # line, but it *can* fit on to the next (empty) line.
                append(start)
                cell_offset = chunk_width

    return break_positions