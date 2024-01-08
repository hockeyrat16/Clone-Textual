"""A view into a Document which wraps the document at a certain
width and can be queried to retrieve lines from the *wrapped* version
of the document.

Allows for incremental updates, ensuring that we only re-wrap ranges of the document
that were influenced by edits.
"""
from __future__ import annotations

from bisect import bisect_right

from rich._wrap import divide_line
from rich.text import Text

from textual._cells import cell_len, cell_width_to_column_index
from textual.document._document import DocumentBase, Location
from textual.expand_tabs import expand_tabs_inline
from textual.geometry import Offset, clamp

VerticalOffset = int
LineIndex = int
SectionOffset = int


class WrappedDocument:
    def __init__(
        self,
        document: DocumentBase,
        width: int = 0,
    ) -> None:
        """Construct a WrappedDocument.

        By default, a WrappedDocument is wrapped with width=0 (no wrapping).
        To wrap the document, use the wrap() method.

        Args:
            document: The document to wrap.
            width: The width to wrap at.
        """
        self.document = document
        """The document wrapping is performed on."""

        self._wrap_offsets: list[list[int]] = []
        """Maps line indices to the offsets within the line where wrapping
        breaks should be added."""

        self._offset_to_line_info: list[tuple[LineIndex, SectionOffset]] = []
        """Maps y_offsets (from the top of the document) to line_index and the offset
        of the section within the line."""

        self._line_index_to_offsets: list[list[VerticalOffset]] = []
        """Maps line indices to all the vertical offsets which correspond to that line."""

        # self._offset_to_section_offset: dict[int, int] = {}
        # """Maps y_offsets to the offsets of the section within the line."""

        self._width: int = width
        """The width the document is currently wrapped at. This will correspond with
        the value last passed into the `wrap` method."""

        self.wrap(width)

    def wrap(self, width: int) -> None:
        """Wrap and cache all lines in the document.

        Args:
            width: The width to wrap at. 0 for no wrapping.
        """
        self._width = width

        # We're starting wrapping from scratch
        new_wrap_offsets: list[list[int]] = []
        offset_to_line_info: list[tuple[LineIndex, SectionOffset]] = []
        line_index_to_offsets: list[list[VerticalOffset]] = []

        append_wrap_offset = new_wrap_offsets.append
        current_offset = 0

        for line_index, line in enumerate(self.document.lines):
            wrap_offsets = divide_line(line, width) if width else []
            append_wrap_offset(wrap_offsets)
            line_index_to_offsets.append([])
            for section_y_offset in range(len(wrap_offsets) + 1):
                offset_to_line_info.append((line_index, section_y_offset))
                line_index_to_offsets[line_index].append(current_offset)
                current_offset += 1

        self._offset_to_line_info = offset_to_line_info
        self._line_index_to_offsets = line_index_to_offsets
        self._wrap_offsets = new_wrap_offsets

    @property
    def lines(self) -> list[list[str]]:
        """The lines of the wrapped version of the Document.

        Each index in the returned list represents a line index in the raw
        document. The list[str] at each index is the content of the raw document line
        split into multiple lines via wrapping.

        Returns:
            A list of lines from the wrapped version of the document.
        """
        wrapped_lines: list[list[str]] = []
        append = wrapped_lines.append
        for line_index, line in enumerate(self.document.lines):
            divided = Text(line).divide(self._wrap_offsets[line_index])
            append([section.plain for section in divided])

        return wrapped_lines

    @property
    def height(self) -> int:
        """The height of the wrapped document."""
        return sum(len(offsets) + 1 for offsets in self._wrap_offsets)

    def wrap_range(
        self,
        start: Location,
        old_end: Location,
        new_end: Location,
    ) -> None:
        """Incrementally recompute wrapping based on a performed edit.

        This must be called *after* the source document has been edited.

        Args:
            start: The start location of the edit that was performed in document-space.
            old_end: The old end location of the edit in document-space.
            new_end: The new end location of the edit in document-space.
        """

        # Get all the text on the lines between start and end in document space

        start_line_index, _ = start
        old_end_line_index, _ = old_end
        new_end_line_index, _ = new_end

        # Although end users should not be able to edit invalid ranges via a TextArea,
        #  programmers can pass whatever they wish to the edit API, so we need to clamp
        #  the edit ranges here to ensure we only attempt to update within the bounds
        #  of the wrapped document.
        old_max_index = len(self._line_index_to_offsets) - 1
        new_max_index = self.document.line_count - 1

        start_line_index = clamp(
            start_line_index, 0, min((old_max_index, new_max_index))
        )
        old_end_line_index = clamp(old_end_line_index, 0, old_max_index)
        new_end_line_index = clamp(new_end_line_index, 0, new_max_index)

        top_line_index, old_bottom_line_index = sorted(
            (start_line_index, old_end_line_index)
        )
        new_bottom_line_index = max((start_line_index, new_end_line_index))

        top_y_offset = self._line_index_to_offsets[top_line_index][0]
        old_bottom_y_offset = self._line_index_to_offsets[old_bottom_line_index][-1]

        # Get the new range of the edit from top to bottom.
        new_lines = self.document.lines[top_line_index : new_bottom_line_index + 1]

        new_wrap_offsets: list[list[int]] = []
        new_line_index_to_offsets: list[list[VerticalOffset]] = []
        new_offset_to_line_info: list[tuple[LineIndex, SectionOffset]] = []
        append_wrap_offsets = new_wrap_offsets.append
        width = self._width

        # Add the new offsets between the top and new bottom (the new post-edit offsets)
        current_y_offset = top_y_offset
        for line_index, line in enumerate(new_lines, top_line_index):
            wrap_offsets = divide_line(line, width) if width else []
            append_wrap_offsets(wrap_offsets)

            # Collect up the new y offsets for this document line
            y_offsets_for_line: list[int] = []
            for section_offset in range(len(wrap_offsets) + 1):
                y_offsets_for_line.append(current_y_offset)
                new_offset_to_line_info.append((line_index, section_offset))
                current_y_offset += 1

            # Save the new y offsets for this line
            new_line_index_to_offsets.append(y_offsets_for_line)

        # Replace the range start -> old with the new wrapped lines
        self._offset_to_line_info[
            top_y_offset : old_bottom_y_offset + 1
        ] = new_offset_to_line_info

        self._line_index_to_offsets[
            top_line_index : old_bottom_line_index + 1
        ] = new_line_index_to_offsets

        # How much did the edit/rewrap alter the offsets?
        old_height = old_bottom_y_offset - top_y_offset + 1
        new_height = len(new_offset_to_line_info)

        offset_shift = new_height - old_height
        line_shift = new_bottom_line_index - old_bottom_line_index

        # Update the line info at all offsets below the edit region.
        if line_shift:
            for y_offset in range(
                top_y_offset + new_height, len(self._offset_to_line_info)
            ):
                old_line_index, section_offset = self._offset_to_line_info[y_offset]
                new_line_index = old_line_index + line_shift
                new_line_info = (new_line_index, section_offset)
                self._offset_to_line_info[y_offset] = new_line_info

        # Update the offsets at all lines below the edit region
        if offset_shift:
            for line_index in range(
                top_line_index + len(new_lines), len(self._line_index_to_offsets)
            ):
                old_offsets = self._line_index_to_offsets[line_index]
                new_offsets = [offset + offset_shift for offset in old_offsets]
                self._line_index_to_offsets[line_index] = new_offsets

        self._wrap_offsets[
            top_line_index : old_bottom_line_index + 1
        ] = new_wrap_offsets

    def offset_to_location(self, offset: Offset, tab_width: int) -> Location:
        """Given an offset within the wrapped/visual display of the document,
        return the corresponding location in the document.

        Args:
            offset: The y-offset within the document.
            tab_width: The maximum width of tab characters in the document.

        Raises:
            ValueError: When the given offset does not correspond to a line
                in the document.

        Returns:
            The Location in the document corresponding to the given offset.
        """
        x, y = offset
        x = max(0, x)
        y = max(0, y)

        if not self._width:
            # No wrapping, so we directly map offset to location and clamp.
            line_index = min(y, len(self._wrap_offsets) - 1)
            column_index = min(x, len(self.document.get_line(line_index)))
            return line_index, column_index

        # Find the line corresponding to the given y offset in the wrapped document.
        get_target_document_column = self.get_target_document_column

        try:
            offset_data = self._offset_to_line_info[y]
        except IndexError:
            # y-offset is too large
            offset_data = self._offset_to_line_info[-1]

        if offset_data is not None:
            line_index, section_y = offset_data
            location = line_index, get_target_document_column(
                line_index,
                x,
                section_y,
                tab_width,
            )
        else:
            location = len(self._wrap_offsets) - 1, get_target_document_column(
                -1, x, -1, tab_width
            )

        # Offset doesn't match any line => land on bottom wrapped line
        return location

    def location_to_offset(self, location: Location, tab_width: int) -> Offset:
        """
        Convert a location in the document to an offset within the wrapped/visual display of the document.

        Args:
            location: The location in the document.
            tab_width: The maximum width of tab characters in the document.

        Returns:
            The Offset in the document's visual display corresponding to the given location.
        """
        line_index, column_index = location

        # Clamp the line index to the bounds of the document
        line_index = clamp(line_index, 0, len(self._line_index_to_offsets))

        # Find the section index of this location, so that we know which y_offset to use
        wrap_offsets = self.get_offsets(line_index)
        section_start_columns = [0, *wrap_offsets]
        section_index = bisect_right(wrap_offsets, column_index)

        # Get the y-offsets corresponding to this line index
        y_offsets = self._line_index_to_offsets[line_index]
        section_column_index = column_index - section_start_columns[section_index]

        section = self.get_sections(line_index)[section_index]
        x_offset = cell_len(
            expand_tabs_inline(section[:section_column_index], tab_width)
        )

        return Offset(x_offset, y_offsets[section_index])

    def get_target_document_column(
        self,
        line_index: int,
        x_offset: int,
        y_offset: int,
        tab_width: int,
    ) -> int:
        """Given a line index and the offsets within the wrapped version of that
        line, return the corresponding column index in the raw document.

        Args:
             line_index: The index of the line in the document.
             x_offset: The x-offset within the wrapped line.
             y_offset: The y-offset within the wrapped line (supports negative indexing).
             tab_width: The size of the tab stop.

        Returns:
            The column index corresponding to the line index and y offset.
        """

        # We've found the relevant line, now find the character by
        # looking at the character corresponding to the offset width.
        sections = self.get_sections(line_index)

        # wrapped_section is the text that appears on a single y_offset within
        # the TextArea. It's a potentially wrapped portion of a larger line from
        # the original document.
        target_section = sections[y_offset]

        # Add the offsets from the wrapped sections above this one (from the same raw
        # document line)
        target_section_start = sum(
            len(wrapped_section) for wrapped_section in sections[:y_offset]
        )

        # Get the column index within this wrapped section of the line
        target_column_index = target_section_start + cell_width_to_column_index(
            target_section, x_offset, tab_width
        )

        # If we're on the final section of a line, the cursor can legally rest beyond
        # the end by a single cell. Otherwise, we'll need to ensure that we're
        # keeping the cursor within the bounds of the target section.
        if y_offset != len(sections) - 1 and y_offset != -1:
            target_column_index = min(
                target_column_index, target_section_start + len(target_section) - 1
            )

        return target_column_index

    def get_sections(self, line_index: int) -> list[str]:
        line_offsets = self._wrap_offsets[line_index]
        wrapped_lines = Text(self.document[line_index]).divide(line_offsets)
        return [line.plain for line in wrapped_lines]

    def get_offsets(self, line_index: int) -> list[int]:
        """Given a line index, get the offsets within that line where wrapping
        should occur for the current document.

        Args:
            line_index: The index of the line within the document.

        Raises:
            ValueError: When `line_index` is out of bounds.

        Returns:
            The offsets within the line where wrapping should occur.
        """
        wrap_offsets = self._wrap_offsets
        out_of_bounds = line_index < 0 or line_index >= len(wrap_offsets)
        if out_of_bounds:
            raise ValueError(
                f"The document line index {line_index!r} is out of bounds. "
                f"The document contains {len(wrap_offsets)!r} lines."
            )
        return wrap_offsets[line_index]