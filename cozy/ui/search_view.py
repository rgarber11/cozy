import threading
from typing import Callable, Sequence

from gi.repository import Adw, Gtk

from cozy.ext import inject
from cozy.model.book import Book
from cozy.ui.widgets.book_row import BookRow
from cozy.ui.widgets.search_results import ArtistResultRow
from cozy.view_model.search_view_model import SearchViewModel
from cozy.ui.headerbar import Headerbar


@Gtk.Template.from_resource("/com/github/geigi/cozy/search_page.ui")
class SearchView(Adw.Bin):
    __gtype_name__ = "SearchView"

    stack: Gtk.Stack = Gtk.Template.Child()
    search_scroller: Gtk.ScrolledWindow = Gtk.Template.Child()
    start_searching_page: Adw.StatusPage = Gtk.Template.Child()
    nothing_found_page: Adw.StatusPage = Gtk.Template.Child()

    book_result_box: Adw.PreferencesGroup = Gtk.Template.Child()
    author_result_box: Adw.PreferencesGroup = Gtk.Template.Child()
    reader_result_box: Adw.PreferencesGroup = Gtk.Template.Child()

    book_result_list: Gtk.ListBox = Gtk.Template.Child()
    author_result_list: Gtk.ListBox = Gtk.Template.Child()
    reader_result_list: Gtk.ListBox = Gtk.Template.Child()

    view_model = inject.attr(SearchViewModel)

    search_thread: threading.Thread
    search_thread_stop: threading.Event

    def __init__(self, main_window_builder: Gtk.Builder, headerbar: Headerbar) -> None:
        super().__init__()

        self.library_stack: Gtk.Stack = main_window_builder.get_object("library_stack")
        self.library_stack.add_child(self)

        self.split_view: Gtk.Stack = main_window_builder.get_object("split_view")

        self.search_bar = headerbar.search_bar
        self.entry = headerbar.search_entry
        self.entry.connect("search-changed", self._on_search_changed)

        self.search_thread = threading.Thread(target=self.view_model.search, name="SearchThread")
        self.search_thread_stop = threading.Event()

        self.view_model.bind_to("close", self.close)

    def close(self) -> None:
        self.library_stack.set_visible_child(self.split_view)
        self.search_bar.set_search_mode(False)

    def on_state_changed(self, widget: Gtk.Widget, param) -> None:
        if widget.get_property(param.name):
            self.library_stack.set_visible_child(self)
        else:
            self.close()

    def _on_search_changed(self, _) -> None:
        self.search_thread_stop.set()

        search_query = self.entry.get_text()
        if search_query:
            if self.search_thread.is_alive():
                self.search_thread.join(timeout=0.2)

            self.search_thread_stop.clear()
            self.search_thread = threading.Thread(
                target=self.view_model.search,
                args=(search_query, self._display_results, self.search_thread_stop),
            )
            self.search_thread.start()
        else:
            self.stack.set_visible_child(self.start_searching_page)

    def _display_results(self, books: list[Book], authors: list[str], readers: list[str]) -> None:
        if any((books, authors, readers)):
            self.stack.set_visible_child(self.search_scroller)
            self._populate_listbox(
                books,
                self.book_result_list,
                self.book_result_box,
                BookRow,
                self.view_model.jump_to_book,
            )
            self._populate_listbox(
                authors,
                self.author_result_list,
                self.author_result_box,
                ArtistResultRow,
                self.view_model.jump_to_author,
            )
            self._populate_listbox(
                readers,
                self.reader_result_list,
                self.reader_result_box,
                ArtistResultRow,
                self.view_model.jump_to_reader,
            )
        else:
            self.stack.set_visible_child(self.nothing_found_page)

    def _populate_listbox(
        self,
        results: Sequence[str | Book],
        listbox: Gtk.ListBox,
        box: Adw.PreferencesGroup,
        row_type: type[BookRow | ArtistResultRow],
        callback: Callable[[str | Book], None],
    ) -> None:
        box.set_visible(False)
        listbox.remove_all()

        if not results:
            return

        box.set_visible(True)

        for result in results:
            if self.search_thread_stop.is_set():
                return

            listbox.append(row_type(result, callback))
