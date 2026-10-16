"""Minimal PDF writers for synthetic fixtures: text pages, image-only scans, embedded e-invoice XML."""

import struct


def _pdf(objects):
    """objects: list of bytes bodies; object n is objects[n-1]. Object 1 is the catalog."""
    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for n, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def _stream(data, extra=b""):
    return b"<< /Length " + str(len(data)).encode() + b" " + extra + b" >>\nstream\n" + data + b"\nendstream"


def _esc(s):
    return s.encode("cp1252").replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _content(lines):
    ops = [b"BT /F1 10 Tf 12 TL 40 800 Td"]
    for line in lines:
        ops.append(b"(" + _esc(line) + b") Tj T*")
    ops.append(b"ET")
    return b"\n".join(ops)


def text_pdf(pages, attachment=None):
    """pages: list of pages, each a list of text lines. attachment: (name, bytes) embedded file."""
    n_pages = len(pages)
    font = 3
    first_page = 4
    page_ids = [first_page + 2 * i for i in range(n_pages)]
    names = b""
    extra = []
    if attachment:
        ef = first_page + 2 * n_pages
        spec = ef + 1
        name, data = attachment
        extra = [_stream(data, b"/Type /EmbeddedFile /Subtype /text#2Fxml"),
                 f"<< /Type /Filespec /F ({name}) /UF ({name}) /AFRelationship /Alternative /EF << /F {ef} 0 R >> >>".encode()]
        names = f" /Names << /EmbeddedFiles << /Names [({name}) {spec} 0 R] >> >> /AF [{spec} 0 R]".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R" + names + b" >>",
            f"<< /Type /Pages /Kids [{' '.join(f'{p} 0 R' for p in page_ids)}] /Count {n_pages} >>".encode(),
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"]
    for i, lines in enumerate(pages):
        content_id = page_ids[i] + 1
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 {font} 0 R >> >> "
                    f"/Contents {content_id} 0 R >>".encode())
        objs.append(_stream(_content(lines)))
    return _pdf(objs + extra)


def jpeg_size(data):
    i = 2
    while i < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        length = struct.unpack(">H", data[i + 2:i + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h, data[i + 9]
        i += 2 + length
    raise ValueError("no JPEG frame header")


def image_pdf(jpeg):
    """A scan: one page holding only a JPEG image, no text layer."""
    w, h, comps = jpeg_size(jpeg)
    cs = b"/DeviceGray" if comps == 1 else b"/DeviceRGB"
    content = b"q 595 0 0 842 0 0 cm /Im1 Do Q"
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /XObject << /Im1 4 0 R >> >> /Contents 5 0 R >>",
            _stream(jpeg, f"/Type /XObject /Subtype /Image /Width {w} /Height {h} /BitsPerComponent 8 /Filter /DCTDecode /ColorSpace ".encode() + cs),
            _stream(content)]
    return _pdf(objs)
