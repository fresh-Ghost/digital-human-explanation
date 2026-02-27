import io
from pypdf import PdfReader

def parse_pdf(content: bytes) -> str:
    """解析 PDF 文件内容"""
    pdf_reader = PdfReader(io.BytesIO(content))
    text_parts = []
    for page in pdf_reader.pages:
        page_text = page.extract_text()
        if page_text.strip():
            text_parts.append(page_text)
    return "\n\n".join(text_parts)
