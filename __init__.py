"""Add-on entry point: adds a "DeckTales" item to Anki's menu bar."""

from aqt import mw

# Qt action class used for the menu item
from aqt.qt import QAction

# Helper that connects a Qt signal to a callback
from aqt.utils import qconnect

from decktales.decktales import DecktalesWindow


def init_decktales_window() -> None:
    """Create and show the DeckTales window."""
    # Stored on mw so the window isn't garbage-collected when this function returns
    mw.decktales_window = DecktalesWindow()
    mw.decktales_window.show()


# create a new menu item
menu_action = QAction("DeckTales", mw)
# set it to call init_decktales_window when it's clicked
qconnect(menu_action.triggered, init_decktales_window)
# and add it to the menu
mw.form.menubar.addAction(menu_action)
