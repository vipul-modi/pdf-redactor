from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem
from PyQt5.QtGui import QPixmap, QImage, QPen, QBrush, QColor
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal
import fitz  # PyMuPDF


class RedactionRect(QGraphicsRectItem):
    """A draggable, deletable redaction rectangle."""

    def __init__(self, rect: QRectF, parent=None):
        super().__init__(rect, parent)
        self.setPen(QPen(QColor(255, 0, 0), 2, Qt.SolidLine))
        self.setBrush(QBrush(QColor(0, 0, 0, 100)))
        self.setFlag(QGraphicsRectItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsRectItem.ItemIsMovable, True)
        self.setCursor(Qt.SizeAllCursor)


class PdfViewer(QGraphicsView):
    """QGraphicsView-based PDF viewer with rectangle drawing for redaction."""

    page_changed = pyqtSignal(int, int)  # current_page, total_pages
    redaction_count_changed = pyqtSignal(int)  # number of rects on current page

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(
            self.renderHints()
        )
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        self._doc: fitz.Document | None = None
        self._current_page = 0
        self._zoom = 2.0  # render scale factor
        self._pixmap_item = None

        # Rectangle drawing state
        self._drawing = False
        self._draw_start: QPointF | None = None
        self._current_rect_item: RedactionRect | None = None
        self._drawing_enabled = True

        # Per-page redaction rects: {page_idx: [RedactionRect, ...]}
        self._page_rects: dict[int, list[RedactionRect]] = {}

    # --- Document loading ---

    def load_document(self, path: str) -> None:
        self._doc = fitz.open(path)
        self._current_page = 0
        self._page_rects.clear()
        self._render_page()

    @property
    def document(self) -> fitz.Document | None:
        return self._doc

    @property
    def current_page(self) -> int:
        return self._current_page

    @property
    def total_pages(self) -> int:
        return len(self._doc) if self._doc else 0

    # --- Page navigation ---

    def go_to_page(self, page_idx: int) -> None:
        if self._doc and 0 <= page_idx < len(self._doc):
            self._save_current_rects()
            self._current_page = page_idx
            self._render_page()

    def next_page(self) -> None:
        self.go_to_page(self._current_page + 1)

    def prev_page(self) -> None:
        self.go_to_page(self._current_page - 1)

    # --- Zoom ---

    def zoom_in(self) -> None:
        self._zoom = min(self._zoom * 1.25, 8.0)
        self._render_page()

    def zoom_out(self) -> None:
        self._zoom = max(self._zoom / 1.25, 0.5)
        self._render_page()

    # --- Drawing toggle ---

    def set_drawing_enabled(self, enabled: bool) -> None:
        self._drawing_enabled = enabled
        if enabled:
            self.setCursor(Qt.CrossCursor)
            self.setDragMode(QGraphicsView.NoDrag)
        else:
            self.setCursor(Qt.ArrowCursor)

    # --- Rendering ---

    def _render_page(self) -> None:
        if not self._doc:
            return
        self._scene.clear()
        self._pixmap_item = None

        page = self._doc[self._current_page]
        mat = fitz.Matrix(self._zoom, self._zoom)
        pix = page.get_pixmap(matrix=mat)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(img)
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(QRectF(pixmap.rect()))

        # Restore rects for this page
        self._restore_current_rects()
        self.page_changed.emit(self._current_page, len(self._doc))
        self._emit_rect_count()

    # --- Rect persistence across page changes ---

    def _save_current_rects(self) -> None:
        """Save scene rects for the current page."""
        rects = [item for item in self._scene.items() if isinstance(item, RedactionRect)]
        self._page_rects[self._current_page] = []
        for r in rects:
            self._page_rects[self._current_page].append(r)
            self._scene.removeItem(r)

    def _restore_current_rects(self) -> None:
        """Restore saved rects for the current page."""
        for r in self._page_rects.get(self._current_page, []):
            self._scene.addItem(r)

    # --- Redaction rect management ---

    def remove_selected_rects(self) -> None:
        """Remove selected redaction rectangles."""
        for item in self._scene.selectedItems():
            if isinstance(item, RedactionRect):
                self._scene.removeItem(item)
                if self._current_page in self._page_rects:
                    if item in self._page_rects[self._current_page]:
                        self._page_rects[self._current_page].remove(item)
        self._emit_rect_count()

    def clear_page_rects(self) -> None:
        """Remove all redaction rects on the current page."""
        for item in list(self._scene.items()):
            if isinstance(item, RedactionRect):
                self._scene.removeItem(item)
        self._page_rects[self._current_page] = []
        self._emit_rect_count()

    def get_all_redactions(self) -> dict[int, list[tuple[float, float, float, float]]]:
        """Return all redaction rects in PDF coordinate space for all pages."""
        self._save_current_rects()
        result: dict[int, list[tuple[float, float, float, float]]] = {}
        for page_idx, rects in self._page_rects.items():
            if not rects:
                continue
            pdf_rects = []
            for r in rects:
                scene_rect = r.sceneBoundingRect()
                # Convert from scene (pixel) coords back to PDF coords
                x0 = scene_rect.x() / self._zoom
                y0 = scene_rect.y() / self._zoom
                x1 = (scene_rect.x() + scene_rect.width()) / self._zoom
                y1 = (scene_rect.y() + scene_rect.height()) / self._zoom
                pdf_rects.append((x0, y0, x1, y1))
            result[page_idx] = pdf_rects
        # Restore so scene still shows them
        self._restore_current_rects()
        return result

    def _emit_rect_count(self) -> None:
        count = sum(1 for item in self._scene.items() if isinstance(item, RedactionRect))
        self.redaction_count_changed.emit(count)

    # --- Ctrl+scroll wheel zoom ---

    def wheelEvent(self, event) -> None:
        if event.modifiers() == Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            elif event.angleDelta().y() < 0:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)

    # --- Mouse events for rectangle drawing ---

    def mousePressEvent(self, event) -> None:
        if self._drawing_enabled and event.button() == Qt.LeftButton:
            # Check if clicking on an existing rect (for selection/move)
            item = self.itemAt(event.pos())
            if isinstance(item, RedactionRect):
                super().mousePressEvent(event)
                return
            # Start drawing a new rect
            self._drawing = True
            self._draw_start = self.mapToScene(event.pos())
            self._current_rect_item = RedactionRect(QRectF(self._draw_start, self._draw_start))
            self._scene.addItem(self._current_rect_item)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drawing and self._current_rect_item and self._draw_start:
            current_pos = self.mapToScene(event.pos())
            rect = QRectF(self._draw_start, current_pos).normalized()
            self._current_rect_item.setRect(rect)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._drawing and event.button() == Qt.LeftButton:
            self._drawing = False
            if self._current_rect_item:
                rect = self._current_rect_item.rect()
                # Remove if too small (accidental click)
                if rect.width() < 5 and rect.height() < 5:
                    self._scene.removeItem(self._current_rect_item)
                else:
                    # Track it for the current page
                    if self._current_page not in self._page_rects:
                        self._page_rects[self._current_page] = []
                    self._page_rects[self._current_page].append(self._current_rect_item)
            self._current_rect_item = None
            self._draw_start = None
            self._emit_rect_count()
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Delete:
            self.remove_selected_rects()
        else:
            super().keyPressEvent(event)
