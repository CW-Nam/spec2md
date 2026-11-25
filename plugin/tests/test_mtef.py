"""OLE equations: MTEF v3/v5 -> LaTeX, and the end-to-end path through a docx."""
import json
import struct

import pytest

from docx_builder import PNG, build, cell, p, row, table
from spec2md import mtef

V3_HEAD = bytes([3, 1, 1, 3, 10])
V5_HEAD = bytes([5, 1, 0, 6, 9]) + b"DSMT6\x00" + b"\x01"
END = b"\x00"


def native(mtef_bytes):
    """EQNOLEFILEHDR (28 bytes) + MTEF."""
    hdr = struct.pack("<HIHIIIII", 28, 0x00020000, 0xC1C0, len(mtef_bytes), 0, 0, 0, 0)
    return hdr + mtef_bytes


def v3_char(tf, ch, opt=0):
    return bytes([0x02 | (opt << 4), tf + 128]) + struct.pack("<H", ord(ch))


def v3_line(*items):
    return b"\x01" + b"".join(items) + END


V3_NULL_LINE = b"\x11"


def v3_tmpl(sel, var, *slots):
    return bytes([0x03, sel, var, 0]) + b"".join(slots) + END


VAR, NUM, FN, SYM, TEXT, EXPAND = 3, 8, 2, 6, 1, 22

V3_CASES = [
    # x_{1}
    (v3_line(v3_char(VAR, "x"), v3_tmpl(15, 1, v3_line(v3_char(NUM, "1")), V3_NULL_LINE)), "x_{1}"),
    # x^{2}
    (v3_line(v3_char(VAR, "x"), v3_tmpl(15, 0, V3_NULL_LINE, v3_line(v3_char(NUM, "2")))), "x^{2}"),
    # 1/2 fraction
    (v3_line(v3_tmpl(14, 0, v3_line(v3_char(NUM, "1")), v3_line(v3_char(NUM, "2")))), r"\frac{1}{2}"),
    # sqrt
    (v3_line(v3_tmpl(13, 0, v3_line(v3_char(NUM, "2")), V3_NULL_LINE)), r"\sqrt{2}"),
    # floor with expanding-font fence characters (private code points)
    (v3_line(v3_tmpl(6, 0, v3_line(v3_char(VAR, "x")),
                     bytes([0x02, EXPAND + 128]) + struct.pack("<H", 0xF8F0),
                     bytes([0x02, EXPAND + 128]) + struct.pack("<H", 0xF8FB))),
     r"\left\lfloor x \right\rfloor"),
    # q with over-bar embellishment (EMBELL record + the extra byte Equation Editor writes)
    (v3_line(v3_char(VAR, "q", opt=0x2) + b"\x06\x11\x00" + END), r"\bar{q}"),
    # sum with lower limit: slots main, lower, upper + operator char
    (v3_line(v3_tmpl(29, 1, v3_line(v3_char(VAR, "a")), v3_line(v3_char(VAR, "i"), v3_char(SYM, "="),
                                                                    v3_char(NUM, "0")),
                     V3_NULL_LINE, v3_char(SYM, "∑"))), r"\sum_{i=0}{a}"),
    # function and text typefaces, Greek
    (v3_line(v3_char(FN, "m"), v3_char(FN, "o"), v3_char(FN, "d"), v3_char(VAR, "μ"),
             v3_char(TEXT, "H"), v3_char(TEXT, "z")), r"\mathrm{mod}\mu\text{Hz}"),
    # 2x2 matrix in brackets: MATRIX rows=2 cols=2, 1 byte row parts, 1 byte col parts
    (v3_line(v3_tmpl(3, 0, v3_line(bytes([0x05, 1, 1, 1, 2, 2, 0, 0])
                                   + v3_line(v3_char(NUM, "1")) + v3_line(v3_char(NUM, "0"))
                                   + v3_line(v3_char(NUM, "0")) + v3_line(v3_char(NUM, "1")) + END))),
     r"\left[ \begin{matrix}1 & 0 \\ 0 & 1\end{matrix} \right]"),
]


@pytest.mark.parametrize("body,expected", V3_CASES)
def test_mtef_v3(body, expected):
    data = native(V3_HEAD + b"\x0a" + body + END)
    assert mtef.to_latex(data) == expected


def v5_line(*items):
    return b"\x01\x00" + b"".join(items) + END


def v5_char(tf, ch):
    return bytes([0x02, 0x00, tf + 128]) + struct.pack("<H", ord(ch))


def test_mtef_v5_with_definition_records():
    defs = (b"\x13WinAllBasicCodePages\x00"   # ENCODING_DEF
            b"\x11\x01Times New Roman\x00"     # FONT_DEF
            b"\x08\x01\x00"                    # FONT_STYLE_DEF
            b"\x09\x64\x00\x00\x01"            # SIZE (lsize 100: byte + word)
            b"\x0a")                           # FULL
    sub = bytes([0x03, 0x00, 27, 0, 0]) + v5_line(v5_char(NUM, "1")) + b"\x01\x01" + END
    frac = bytes([0x03, 0x00, 11, 0, 0]) + v5_line(v5_char(VAR, "a")) + v5_line(v5_char(VAR, "b")) + END
    data = native(V5_HEAD + defs + v5_line(v5_char(VAR, "x"), sub, v5_char(SYM, "="), frac) + END)
    assert mtef.to_latex(data) == r"x_{1}=\frac{a}{b}"


def test_unknown_template_raises():
    data = native(V3_HEAD + v3_line(v3_tmpl(40, 0, v3_line(v3_char(NUM, "1")))) + END)
    with pytest.raises(mtef.MtefError, match="v3 tmpl 40"):
        mtef.to_latex(data)


# ---------------------------------------------------------------------------
# minimal compound file (CFB v3, 512-byte sectors, one stream >= 4096 bytes)
# ---------------------------------------------------------------------------
def cfb(stream_name, data):
    data = data + b"\x00" * (4096 - len(data)) if len(data) < 4096 else data
    nsec = (len(data) + 511) // 512
    free, end, fatsect = 0xFFFFFFFF, 0xFFFFFFFE, 0xFFFFFFFD
    hdr = bytearray(512)
    hdr[0:8] = bytes.fromhex("D0CF11E0A1B11AE1")
    struct.pack_into("<HHHHH", hdr, 24, 0x3E, 3, 0xFFFE, 9, 6)
    struct.pack_into("<IIIIIIII", hdr, 40, 0, 1, 1, 0, 4096, end, 0, end)
    struct.pack_into("<I", hdr, 76, 0)  # DIFAT[0] = FAT in sector 0
    for i in range(1, 109):
        struct.pack_into("<I", hdr, 76 + 4 * i, free)
    fat = [fatsect, end] + [3 + i for i in range(nsec - 1)] + [end]
    fat += [free] * (128 - len(fat))
    fat_sec = struct.pack("<128I", *fat)

    def entry(name, typ, child, start, size):
        e = bytearray(128)
        n = (name + "\x00").encode("utf-16-le") if name else b""
        e[0:len(n)] = n
        struct.pack_into("<HBB", e, 64, len(n), typ, 1)
        struct.pack_into("<III", e, 68, free, free, child)
        struct.pack_into("<II", e, 116, start, size)
        return bytes(e)
    dirs = (entry("Root Entry", 5, 1, end, 0) + entry(stream_name, 2, free, 2, len(data))
            + entry("", 0, free, 0, 0) + entry("", 0, free, 0, 0))
    body = data + b"\x00" * (nsec * 512 - len(data))
    return bytes(hdr) + fat_sec + dirs + body


def test_cfb_round_trip():
    stream = native(V3_HEAD + b"\x0a" + V3_CASES[0][0] + END)
    assert mtef.read_equation_native(cfb("Equation Native", stream))[:len(stream)] == stream


def ole_object(ole_rid, img_rid, prog="Equation.3"):
    return (f'<w:r><w:object><v:shape id="s{ole_rid}"><v:imagedata r:id="{img_rid}" o:title=""/></v:shape>'
            f'<o:OLEObject Type="Embed" ProgID="{prog}" ShapeID="s{ole_rid}" r:id="{ole_rid}"/></w:object></w:r>')


def test_docx_ole_equations(tmp_path, convert):
    good = cfb("Equation Native", native(V3_HEAD + b"\x0a" + V3_CASES[0][0] + END))
    frac = cfb("Equation Native", native(V3_HEAD + b"\x0a" + V3_CASES[2][0] + END))
    bad = cfb("Equation Native", native(V3_HEAD + v3_line(v3_tmpl(40, 0, v3_line(v3_char(NUM, "1")))) + END))
    body = "".join([
        p("Heading1", "1\tScope"),
        p("Normal", "index ", ole_object("rIdO1", "rIdI1"), " is used."),
        p("EQ", "\t", ole_object("rIdO2", "rIdI2")),
        p("Normal", "broken ", ole_object("rIdO3", "rIdI3"), "."),
        table(1, row(cell(p("TAL", "cell ", ole_object("rIdO1", "rIdI1"))))),
    ])
    media = {"rIdI1": ("image1.wmf", b"W1"), "rIdI2": ("image2.wmf", b"W2"), "rIdI3": ("image3.wmf", b"W3")}
    path = build(tmp_path / "39995-i00.docx", body, media)
    _add_embeddings(path, {"rIdO1": ("oleObject1.bin", good), "rIdO2": ("oleObject2.bin", frac),
                           "rIdO3": ("oleObject3.bin", bad)})
    out, conv = convert(path)
    text = out.body("1")
    assert "index $x_{1}$<!-- ole-equation: ../media/image1.wmf --> is used." in text
    assert "\n$$\n\\frac{1}{2}\n$$\n<!-- ole-equation: ../media/image2.wmf -->\n" in text
    assert "broken ![equation](../media/image3.wmf)." in text
    assert "<td>cell $x_{1}$<!-- ole-equation: ../media/image1.wmf --></td>" in text
    assert out.manifest["ole_equations"] == {"latex": 3, "image_only": 1}
    assert out.entry("1")["equations"] == 4 and out.entry("1")["figures"] == 0
    assert conv.summary["ole_equation_failures"] == {"v3 tmpl 40": 1}


def _add_embeddings(path, objs):
    """Append OLE parts and their relationships to a fixture docx."""
    import zipfile
    with zipfile.ZipFile(path) as z:
        files = {n: z.read(n) for n in z.namelist()}
    rels = files["word/_rels/document.xml.rels"].decode()
    extra = "".join(
        f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject" '
        f'Target="embeddings/{name}"/>' for rid, (name, _) in objs.items())
    files["word/_rels/document.xml.rels"] = rels.replace("</Relationships>", extra + "</Relationships>").encode()
    for name, data in objs.values():
        files[f"word/embeddings/{name}"] = data
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in files.items():
            z.writestr(n, d)


def test_mtef_empty_pile_matrix_and_scripts_dropped():
    empty_matrix = bytes([0x05, 1, 1, 1, 1, 1, 0, 0]) + v3_line() + END
    body = v3_line(v3_char(FN, "m"), v3_char(FN, "a"), v3_char(FN, "x"),
                   v3_tmpl(2, 0, v3_line(b"\x04\x01\x01" + v3_line() + END)),   # {empty pile}
                   empty_matrix,
                   v3_tmpl(15, 1, V3_NULL_LINE, V3_NULL_LINE))                  # empty script
    assert mtef.to_latex(native(V3_HEAD + body + END)) == r"\mathrm{max}\left\{ \right\}"
