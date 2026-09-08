"""
Useful little PyQt Popup class.

Sample calls,

    Popup a info window with a OK button. popup blocked until button is pressed,
        popup = InfoPopup('Your ini.py list of servers is invalid.', option='BUTTON')
        popup.open_popup()

    Popup an info window with no buttons. Open and close the popup with program flow,
        popup = InfoPopup('Please wait...', option='NO_BUTTON')
        popup.open_popup()
        ... Do some long operation here...
        popup.close_popup()

    You can also update the text on an already created popup with,
        popup.update_text('New Text To Show')

Written by: Steve Hageman - August 2026
    License: https://unlicense.org/
"""
try:
    from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QApplication
    from PyQt6.QtCore import Qt
    WindowContextHelpButtonHint = Qt.WindowType.WindowContextHelpButtonHint
except ImportError:
    from PyQt5.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QApplication
    from PyQt5.QtCore import Qt
    WindowContextHelpButtonHint = Qt.WindowContextHelpButtonHint


class InfoPopup(QDialog):
    def __init__(self, text, option='BUTTON', parent=None):
        super().__init__(parent)

        self.option = option

        self.setWindowTitle("Info")
        self.setModal(True)

        # Remove the "?" help button
        self.setWindowFlags(self.windowFlags() & ~WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)

        self.label = QLabel(text)
        self.label.setWordWrap(True)
        layout.addWidget(self.label)

        if option == 'BUTTON':
            ok_btn = QPushButton("OK")
            ok_btn.clicked.connect(self.accept)
            layout.addWidget(ok_btn)

        self.resize(300, 150)


    def update_text(self, new_text):
        self.label.setText(new_text)
        self.label.repaint()
        self.repaint()
        QApplication.processEvents()


    def open_popup(self):
        if self.option == 'BUTTON':
            # BLOCKING modal dialog
            self.exec()
        else:
            # Non-blocking modal dialog
            self.show()
            QApplication.processEvents()


    def close_popup(self):
        self.close()

# ----- FINI -----
