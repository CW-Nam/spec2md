"""Build small .docx fixtures from WordprocessingML snippets (tests only)."""
import zipfile

NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
      'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
      'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" '
      'xmlns:v="urn:schemas-microsoft-com:vml" '
      'xmlns:o="urn:schemas-microsoft-com:office:office" '
      'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"')

# styleId -> (name, outlineLvl or None, type)
STYLES = {
    "Normal": ("Normal", None, "paragraph"),
    "Heading1": ("heading 1", 0, "paragraph"), "Heading2": ("heading 2", 1, "paragraph"),
    "Heading3": ("heading 3", 2, "paragraph"), "Heading4": ("heading 4", 3, "paragraph"),
    "Heading5": ("heading 5", 4, "paragraph"), "Heading8": ("heading 8", 7, "paragraph"),
    "H6": ("H6", 9, "paragraph"), "TOC1": ("toc 1", None, "paragraph"), "TT": ("TT", None, "paragraph"),
    "ZA": ("ZA", None, "paragraph"), "ZT": ("ZT", None, "paragraph"),
    "B1": ("B1", None, "paragraph"), "B2": ("B2", None, "paragraph"), "B7": ("B7", None, "paragraph"),
    "NO": ("NO", None, "paragraph"), "EX": ("EX", None, "paragraph"), "EW": ("EW", None, "paragraph"),
    "TH": ("TH", None, "paragraph"), "TF": ("TF", None, "paragraph"), "PL": ("PL", None, "paragraph"),
    "TAL": ("TAL", None, "paragraph"), "TAH": ("TAH", None, "paragraph"), "EQ": ("EQ", None, "paragraph"),
    "Weird": ("Weird Style", None, "paragraph"),
    "SupChar": ("Sup Char", None, "character"),
    "ListNumber": ("List Number", None, "paragraph"),
}

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
       b"\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00"
       b"\x00\x00IEND\xaeB`\x82")


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def run(text, rpr=""):
    out = []
    for i, seg in enumerate(text.split("\t")):
        if i:
            out.append("<w:tab/>")
        if seg:
            out.append(f'<w:t xml:space="preserve">{esc(seg)}</w:t>')
    return f"<w:r>{'<w:rPr>' + rpr + '</w:rPr>' if rpr else ''}{''.join(out)}</w:r>"


def p(style, *content, ppr=""):
    body = "".join(c if c.startswith("<") else run(c) for c in content)
    sty = f'<w:pStyle w:val="{style}"/>' if style else ""
    return f"<w:p><w:pPr>{sty}{ppr}</w:pPr>{body}</w:p>"


def cell(*paras, tcpr=""):
    return f"<w:tc><w:tcPr>{tcpr}</w:tcPr>{''.join(paras) or p('TAL')}</w:tc>"


def row(*cells, trpr=""):
    return f"<w:tr>{'<w:trPr>' + trpr + '</w:trPr>' if trpr else ''}{''.join(cells)}</w:tr>"


def table(ncols, *rows):
    grid = "".join('<w:gridCol w:w="1000"/>' for _ in range(ncols))
    return f"<w:tbl><w:tblPr/><w:tblGrid>{grid}</w:tblGrid>{''.join(rows)}</w:tbl>"


def drawing(rid):
    return (f'<w:r><w:drawing><wp:inline><a:graphic><a:graphicData><pic:pic><pic:blipFill>'
            f'<a:blip r:embed="{rid}"/></pic:blipFill></pic:pic></a:graphicData></a:graphic>'
            f'</wp:inline></w:drawing></w:r>')


def ole(rid, prog):
    return (f'<w:r><w:object><v:shape id="s{rid}"><v:imagedata r:id="{rid}" o:title=""/></v:shape>'
            f'<o:OLEObject Type="Embed" ProgID="{prog}" ShapeID="s{rid}"/></w:object></w:r>')


def styles_xml():
    out = []
    for sid, (name, lvl, typ) in STYLES.items():
        ppr = f'<w:pPr><w:outlineLvl w:val="{lvl}"/></w:pPr>' if lvl is not None else ""
        if sid == "ListNumber":
            ppr = '<w:pPr><w:numPr><w:numId w:val="3"/></w:numPr></w:pPr>'
        rpr = '<w:rPr><w:vertAlign w:val="superscript"/></w:rPr>' if sid == "SupChar" else ""
        out.append(f'<w:style w:type="{typ}" w:styleId="{sid}"><w:name w:val="{name}"/>{ppr}{rpr}</w:style>')
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles {NS}>{"".join(out)}</w:styles>'


def build(path, body, media=None):
    """Write a .docx with the given body XML. media: {rId: (name, bytes)}."""
    media = media or {}
    rels = "".join(
        f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
        f'Target="media/{name}"/>' for rid, (name, _) in media.items())
    rels = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            f'{rels}</Relationships>')
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Default Extension="png" ContentType="image/png"/>'
          '<Default Extension="wmf" ContentType="image/x-wmf"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
          '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
          '</Types>')
    root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                 '</Relationships>')
    doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {NS}><w:body>'
           f'{body}<w:sectPr/></w:body></w:document>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("word/document.xml", doc)
        z.writestr("word/styles.xml", styles_xml())
        z.writestr("word/_rels/document.xml.rels", rels)
        for name, data in media.values():
            z.writestr(f"word/media/{name}", data)
    return path


def cover(version="18.1.0", number="38.999"):
    """Cover table with a ZA paragraph split over several runs, then a TOC."""
    za = p("ZA", "3GPP TS ", number.split(".")[0] + ".", number.split(".")[1], f" V{version} ", "(2026-09)")
    return (table(1, row(cell(za)), row(cell(p("ZT", "Technical Specification"))))
            + p("TT", "Contents") + p("TOC1", "1\tScope\t5"))
