from aqt import mw

# import all of the Qt GUI library
from aqt.qt import QAction

# import the "show info" tool from utils.py
from aqt.utils import qconnect

from decktales.decktales import DecktalesWindow


def init_decktales_window() -> None:
    mw.w = DecktalesWindow()
    mw.w.show()


# create a new menu item
action = QAction("DeckTales", mw)
# set it to call init_decktales_window when it's clicked
qconnect(action.triggered, init_decktales_window)
# and add it to the tools menu
mw.form.menuTools.addAction(action)
