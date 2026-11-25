"""XML namespaces used in WordprocessingML documents (Clark notation prefixes)."""

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
V = "{urn:schemas-microsoft-com:vml}"
O = "{urn:schemas-microsoft-com:office:office}"
MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
WPS = "{http://schemas.microsoft.com/office/word/2010/wordprocessingShape}"
PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def local(tag):
    """'{ns}name' -> 'name' (non-string tags such as comments -> '')."""
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]
