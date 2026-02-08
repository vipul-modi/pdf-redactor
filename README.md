# PDF Redactor

A desktop application to visually redact sections of PDF documents and print them.

## Features

- **Open** any PDF file
- **Draw rectangles** over areas to redact (click and drag)
- **Permanent redaction** — underlying content is removed, not just covered
- **Save** the redacted PDF
- **Print** directly from the app via system print dialog
- **Multi-page** support with page navigation
- **Zoom** in/out for precise redaction
- Works on **Windows** and **macOS**

## Requirements

- Python 3.10+
- PyQt5
- PyMuPDF

## Setup

```bash
pip install -r requirements.txt
```

## Usage

**Windows:**
```
launch.bat
```

**macOS/Linux:**
```bash
chmod +x launch.sh
./launch.sh
```

Or run directly:
```bash
python main.py
```

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| Ctrl+O | Open PDF |
| Ctrl+Shift+S | Save redacted PDF |
| Ctrl+P | Print |
| Ctrl+Left/Right | Previous/Next page |
| Ctrl++/- | Zoom in/out |
| Delete | Remove selected redaction rectangle |
| Ctrl+Shift+R | Apply redactions permanently |
