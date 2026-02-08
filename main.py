import sys
from PyQt5.QtWidgets import QApplication
from redactor_app import RedactorApp


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PDF Redactor")
    window = RedactorApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
