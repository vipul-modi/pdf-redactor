import os
import tempfile

from PyQt5.QtWidgets import (
    QMainWindow, QToolBar, QAction, QFileDialog, QLabel,
    QMessageBox, QStatusBar, QSizePolicy,
)
from PyQt5.QtGui import QIcon, QKeySequence, QImage, QPainter
from PyQt5.QtPrintSupport import QPrinter, QPrintPreviewDialog
from PyQt5.QtCore import Qt
import fitz

from pdf_viewer import PdfViewer
from redaction_engine import RedactionEngine


class RedactorApp(QMainWindow):
    """Main application window for PDF Redactor."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Redactor")
        self.resize(1000, 800)

        self._pdf_path: str | None = None

        # Central widget
        self._viewer = PdfViewer(self)
        self.setCentralWidget(self._viewer)
        self._viewer.page_changed.connect(self._on_page_changed)
        self._viewer.redaction_count_changed.connect(self._on_rect_count_changed)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._page_label = QLabel("No document")
        self._rect_label = QLabel("")
        self._status_bar.addWidget(self._page_label)
        self._status_bar.addPermanentWidget(self._rect_label)

        self._build_toolbar()

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # File actions
        open_action = QAction("Open PDF", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self._open_file)
        toolbar.addAction(open_action)

        save_action = QAction("Save Redacted", self)
        save_action.setShortcut(QKeySequence.SaveAs)
        save_action.triggered.connect(self._save_redacted)
        toolbar.addAction(save_action)

        print_action = QAction("Print", self)
        print_action.setShortcut(QKeySequence.Print)
        print_action.triggered.connect(self._print_document)
        toolbar.addAction(print_action)

        toolbar.addSeparator()

        # Page navigation
        prev_action = QAction("◀ Prev", self)
        prev_action.setShortcut(QKeySequence("Ctrl+Left"))
        prev_action.triggered.connect(self._viewer.prev_page)
        toolbar.addAction(prev_action)

        next_action = QAction("Next ▶", self)
        next_action.setShortcut(QKeySequence("Ctrl+Right"))
        next_action.triggered.connect(self._viewer.next_page)
        toolbar.addAction(next_action)

        toolbar.addSeparator()

        # Zoom
        zoom_in_action = QAction("Zoom +", self)
        zoom_in_action.setShortcut(QKeySequence.ZoomIn)
        zoom_in_action.triggered.connect(self._viewer.zoom_in)
        toolbar.addAction(zoom_in_action)

        zoom_out_action = QAction("Zoom −", self)
        zoom_out_action.setShortcut(QKeySequence.ZoomOut)
        zoom_out_action.triggered.connect(self._viewer.zoom_out)
        toolbar.addAction(zoom_out_action)

        toolbar.addSeparator()

        # Redaction management
        delete_sel_action = QAction("Delete Selected", self)
        delete_sel_action.setShortcut(QKeySequence.Delete)
        delete_sel_action.triggered.connect(self._viewer.remove_selected_rects)
        toolbar.addAction(delete_sel_action)

        clear_action = QAction("Clear Page", self)
        clear_action.triggered.connect(self._viewer.clear_page_rects)
        toolbar.addAction(clear_action)

        toolbar.addSeparator()

        # Apply redactions
        apply_action = QAction("Apply Redactions", self)
        apply_action.setShortcut(QKeySequence("Ctrl+Shift+R"))
        apply_action.triggered.connect(self._apply_redactions)
        toolbar.addAction(apply_action)

    # --- Slots ---

    def _on_page_changed(self, current: int, total: int) -> None:
        self._page_label.setText(f"Page {current + 1} / {total}")

    def _on_rect_count_changed(self, count: int) -> None:
        self._rect_label.setText(f"Redaction areas: {count}" if count else "")

    # --- File operations ---

    def _open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", "", "PDF Files (*.pdf)"
        )
        if path:
            self._pdf_path = path
            self._viewer.load_document(path)
            self.setWindowTitle(f"PDF Redactor — {os.path.basename(path)}")

    def _apply_redactions(self) -> None:
        """Apply redactions to the in-memory document and re-render."""
        doc = self._viewer.document
        if not doc:
            QMessageBox.warning(self, "No Document", "Open a PDF first.")
            return

        redactions = self._viewer.get_all_redactions()
        if not redactions:
            QMessageBox.information(self, "No Redactions", "Draw rectangles on the PDF to mark areas for redaction.")
            return

        reply = QMessageBox.question(
            self, "Apply Redactions",
            "This will permanently remove content under the redacted areas.\n\nContinue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        engine = RedactionEngine(doc)
        engine.apply_redactions(redactions)

        # Clear stored rects and re-render
        self._viewer._page_rects.clear()
        self._viewer._render_page()
        self._status_bar.showMessage("Redactions applied successfully.", 5000)

    def _save_redacted(self) -> None:
        doc = self._viewer.document
        if not doc:
            QMessageBox.warning(self, "No Document", "Open a PDF first.")
            return

        default_name = ""
        if self._pdf_path:
            base, ext = os.path.splitext(self._pdf_path)
            default_name = f"{base}_redacted{ext}"

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Redacted PDF", default_name, "PDF Files (*.pdf)"
        )
        if path:
            engine = RedactionEngine(doc)
            engine.save(path)
            self._status_bar.showMessage(f"Saved to {path}", 5000)

    def _print_document(self) -> None:
        """Print the current (possibly redacted) PDF via preview dialog."""
        doc = self._viewer.document
        if not doc:
            QMessageBox.warning(self, "No Document", "Open a PDF first.")
            return

        printer = QPrinter(QPrinter.HighResolution)
        preview = QPrintPreviewDialog(printer, self)
        preview.paintRequested.connect(self._render_for_print)
        preview.exec_()

    def _render_for_print(self, printer: QPrinter) -> None:
        """Render all PDF pages to the printer."""
        doc = self._viewer.document
        if not doc:
            return

        painter = QPainter()
        if not painter.begin(printer):
            return

        try:
            for i in range(len(doc)):
                if i > 0:
                    printer.newPage()
                page = doc[i]
                dpi_scale = printer.resolution() / 72.0
                mat = fitz.Matrix(dpi_scale, dpi_scale)
                pix = page.get_pixmap(matrix=mat)
                img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)

                page_rect = printer.pageRect()
                scaled = img.scaled(
                    page_rect.width(), page_rect.height(),
                    Qt.KeepAspectRatio, Qt.SmoothTransformation,
                )
                x = (page_rect.width() - scaled.width()) // 2
                y = (page_rect.height() - scaled.height()) // 2
                painter.drawImage(x, y, scaled)
        finally:
            painter.end()

        self._status_bar.showMessage("Document sent to printer.", 5000)
