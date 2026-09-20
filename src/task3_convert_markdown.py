"""Task 3 — Chuẩn hóa tài liệu pháp lý và bài viết sang Markdown."""

import json
import re
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit


ROOT_DIR = Path(__file__).parent.parent
LANDING_DIR = ROOT_DIR / "data" / "landing"
OUTPUT_DIR = ROOT_DIR / "data" / "standardized"
MIN_CONTENT_LENGTH: Final = 200
MIN_PDF_TEXT_LENGTH: Final = 500
STANDARDIZATION_VERSION: Final = "clean-v2"

_LEGAL_OCR_REPLACEMENTS: Final = {
    "phát tr iển": "phát triển",
    "bảo t ồ n": "bảo tồn",
    "bản s ắ c": "bản sắc",
    "tr ong": "trong",
    "tr iệu": "triệu",
    "ch o": "cho",
    "đ ờ i": "đời",
    "Xâ y": "Xây",
    "tha o": "thao",
    "đ ề": "đề",
    "xu ấ t": "xuất",
    "h ỗ": "hỗ",
    "đ ầ u": "đầu",
    "c ầ u": "cầu",
    "th ẩm": "thẩm",
    "c ông": "công",
    "nh ận": "nhận",
    "tr ú": "trú",
    "l ịch": "lịch",
    "kh ác": "khác",
    "đ ạt": "đạt",
    "chu ẩn": "chuẩn",
    "ph ép": "phép",
    "d ịch": "dịch",
    "h ành": "hành",
    "qu ốc": "quốc",
    "n ội": "nội",
    "B ộ": "Bộ",
    "T ài": "Tài",
}

LEGAL_METADATA: Final = {
    "luat_du_lich_09_2017_qh14": {
        "title": "Luật Du lịch số 09/2017/QH14",
        "url": "https://vanban.chinhphu.vn/?docid=190290&pageid=27160",
        "transcription_url": "https://luatvietnam.vn/van-hoa/luat-du-lich-2017-luat-so-09-2017-qh14-115518-d1.html",
    },
    "nghi_dinh_168_2017_nd_cp_huong_dan_luat_du_lich": {
        "title": "Nghị định 168/2017/NĐ-CP quy định chi tiết Luật Du lịch",
        "url": "https://vanban.chinhphu.vn/?docid=193059&pageid=27160",
        "transcription_url": "https://luatvietnam.vn/van-hoa/nghi-dinh-168-2017-nd-cp-quy-dinh-chi-tiet-mot-so-dieu-cua-luat-du-lich-160217-d1.html",
    },
    "quyet_dinh_147_qd_ttg_chien_luoc_phat_trien_du_lich_2030": {
        "title": "Quyết định 147/QĐ-TTg về Chiến lược phát triển du lịch đến 2030",
        "url": "https://vanban.chinhphu.vn/?docid=198927&pageid=27160",
        "transcription_url": "https://luatvietnam.vn/van-hoa/quyet-dinh-147-qd-ttg-chien-luoc-phat-trien-du-lich-viet-nam-den-nam-2030-180149-d1.html",
    },
}


def _clean_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\ufeff", "").replace("\xa0", " ").replace("\x0c", "\n\n")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _strip_markdown_media(text: str) -> str:
    """Remove crawler media noise while retaining useful linked text."""
    text = re.sub(r"(?m)^\s*!\[[^\]]*\]\([^\n)]*\).*?$", "", text)
    # A few crawlers emit inline icons rather than a dedicated image line.
    text = re.sub(r"!\[[^\]]*\]\([^\n)]*\)", "", text)
    text = re.sub(r"\[([^\]\n]+)\]\([^\n)]*\)", r"\1", text)
    return text


def _heading_depth(line: str) -> int:
    match = re.match(r"^#\s+(\d+(?:\.\d+)*)\.?(?:\s|$)", line)
    return min(4, 1 + match.group(1).count(".")) if match else 1


def _normalise_article_headings(text: str) -> str:
    """Keep one document H1 and make headings inside the article hierarchical."""
    output: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s*(.*?)\s*$", line)
        if not match:
            output.append(line)
            continue
        source_depth = len(match.group(1))
        label = match.group(2).strip()
        if not label:
            continue
        target_depth = max(2, source_depth)
        if source_depth == 1:
            target_depth = _heading_depth(f"# {label}") + 1
        output.append(f"{'#' * target_depth} {label}")
    return "\n".join(output)


def _slice_between_lines(
    text: str,
    *,
    start_pattern: str | None = None,
    end_patterns: tuple[str, ...] = (),
) -> str:
    lines = text.splitlines()
    start = 0
    if start_pattern:
        matcher = re.compile(start_pattern, re.IGNORECASE)
        for index, line in enumerate(lines):
            if matcher.search(line.strip()):
                start = index + 1
                break

    end = len(lines)
    end_matchers = [re.compile(pattern, re.IGNORECASE) for pattern in end_patterns]
    for index in range(start, len(lines)):
        if any(pattern.search(lines[index].strip()) for pattern in end_matchers):
            end = index
            break
    return "\n".join(lines[start:end])


def _clean_news_markdown(markdown: str, title: str, url: str) -> str:
    """Extract article content and remove menus, ads, widgets and repeated title."""
    text = _clean_text(markdown)
    host = urlsplit(url).netloc.lower().removeprefix("www.")

    if host == "vinpearl.com":
        text = _slice_between_lines(
            text,
            start_pattern=r"^#\s+",
            end_patterns=(r"^Đọc tiếp\s*$", r"^Chia sẻ tin qua:\s*$"),
        )
        text = re.sub(
            r"(?ms)^Sau khi bổ sung đầy năng lượng,.*?^Booking vé[^\n]*\n?",
            "",
            text,
        )
    elif host == "traveloka.com":
        text = _slice_between_lines(
            text,
            start_pattern=r"^#\s+",
            end_patterns=(
                r"^Xem thêm:\s*$",
                r"^Tags:\s*$",
                r"^###\s+(?:Trong bài viết này|Table of Content)\s*$",
            ),
        )
        # Author and reading-time labels precede the actual lead paragraph.
        text = re.sub(
            r"\A\s*[^\n]+\n\s*(?:Dưới\s+\d+\s+phút đọc|Đọc trong khoảng\s+\d+\s+phút)\s*\n",
            "",
            text,
            flags=re.IGNORECASE,
        )
        # Booking widgets embedded between two article sections are not evidence.
        text = re.sub(
            r"(?ms)^#\s+Vé máy bay đi[^\n]*\n.*?(?=^#\s+\d+(?:\.\d+)*\b)",
            "",
            text,
        )
    else:
        # Most article crawls contain a single H1 after breadcrumbs/category labels.
        if re.search(r"(?m)^#\s+", text):
            text = _slice_between_lines(
                text,
                start_pattern=r"^#\s+",
                end_patterns=(r"^#{3,6}\s+Content\b",),
            )

    text = _strip_markdown_media(text)
    text = re.sub(r"(?m)^Posted on .*$", "", text)
    text = re.sub(r"(?m)^\d{2}/\d{2}/\d{4}(?:\s+[\d.]+)?\s*$", "", text)
    text = re.sub(r"(?m)^(?:\d{1,2}|Th\d{1,2})\s*$", "", text)
    text = re.sub(r"(?m)^\s*[•·]\s*", "- ", text)
    text = re.sub(
        r"(?ms)^- Thoải mái di chuyển cùng Duy Khang Limousine:.*?^Xem thêm\s*:.*$",
        "",
        text,
    )
    text = re.sub(
        r"(?m)^Hãy lên kế hoạch ngay.*Duy Khang Limousine.*$",
        "",
        text,
    )
    text = re.sub(r"(?m)\s+Hãy đặt vé máy bay.*$", "", text)
    text = re.sub(r"(?ms)^Để có được chuyến đi Thanh Hóa.*\Z", "", text)
    text = re.sub(r"(?m) Dù bạn lên kế hoạch nghỉ dưỡng.*$", "", text)
    text = _normalise_article_headings(text)
    text = _clean_text(text)
    if len(text) < MIN_CONTENT_LENGTH:
        raise ValueError(f"Nội dung sau làm sạch quá ngắn: {title}")
    return text


def _clean_legal_markdown(text: str) -> str:
    """Remove OCR/page artefacts without guessing or rewriting legal wording."""
    text = _clean_text(text)
    text = re.sub(r"(?m)^Đang theo dõi\s*$", "", text)
    text = re.sub(r"(?m)^.*Theo quy định tại\s*:.*$", "", text)
    text = re.sub(r"(?m)^.*áp dụng từ ngày 01/7/2025 đến hết ngày 28/02/2027\.?$", "", text)
    text = re.sub(
        r"(?m)^Mức ký quỹ .*Nghị định 94/2021/NĐ-CP.*$|^Theo quy định tại Nghị định 94/2021/NĐ-CP:.*$",
        "",
        text,
    )
    text = _strip_markdown_media(text)
    text = text.replace("**", "").replace("_", "")
    # The signed PDFs repeat artificial page labels and OCR page numbers. They
    # hurt retrieval and can split one sentence into unrelated chunks.
    text = re.sub(
        r"(?m)^## Trang \d+\s*\n(?:\s*[:;]?\s*\d{1,3}\s*[».:]?\s*\n)?",
        "",
        text,
    )

    # Discard signature metadata and damaged mastheads before the legal text.
    preamble = re.search(r"(?mi)^Căn cứ\b", text)
    if preamble:
        text = text[preamble.start():]

    # Recipient/signature blocks and scanned annex templates are high-noise
    # administrative matter; the substantive articles end before these lines.
    ending = re.search(
        r"(?mi)^N(?:ơ|o)i nhận:|^;?\s*CHỦ TỊCH QUỐC HỘI\b|^Lu\s+ật\s+n\s+ày\s+đư\s+ợc\b",
        text,
    )
    if ending:
        text = text[:ending.start()]

    text = re.sub(r"(?m)^\s*[:;=_<>¬†„'‘’`~.-]{1,12}\s*$", "", text)
    text = re.sub(r"(?m)^\s*\d{1,2}\s*$", "", text)
    text = re.sub(r"(?m)^\s*[„_]\s*(?=\d+[.,]\s*)", "", text)
    text = re.sub(r"(?m)^(Ch(?:ư|u)ơng\s+[IVXLCDM]+)\s*$", r"## \1", text)
    text = re.sub(r"(?m)^(Mục\s+\d+\.?[^\n]*)$", r"### \1", text)
    text = re.sub(r"(?m)^(Điều\s+\d+[a-zA-Z]?\.[^\n]*)$", r"### \1", text)
    text = re.sub(r"(?m)^([IVXLCDM]+\.\s+[A-ZÀ-Ỹ][A-ZÀ-Ỹ\s,–-]+)$", r"## \1", text)
    text = re.sub(r"(?m)^(#{2,4}\s+Điều\s+\d+[a-zA-Z]?\.)\s*", r"\1 ", text)
    for damaged, corrected in _LEGAL_OCR_REPLACEMENTS.items():
        text = text.replace(damaged, corrected)
    return _clean_text(text)


def _write_atomic(path: Path, content: str) -> None:
    content = content.strip() + "\n"
    if len(content) < MIN_CONTENT_LENGTH:
        raise ValueError(f"Nội dung chuẩn hóa quá ngắn: {path.name}")
    temporary_path = path.with_suffix(path.suffix + ".part")
    try:
        temporary_path.write_text(content, encoding="utf-8")
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _is_fresh(source: Path, output: Path) -> bool:
    try:
        return (
            output.stat().st_mtime_ns >= source.stat().st_mtime_ns
            and len(output.read_text(encoding="utf-8").strip()) >= MIN_CONTENT_LENGTH
        )
    except (OSError, UnicodeError):
        return False


def _convert_with_markitdown(path: Path) -> str:
    try:
        from markitdown import MarkItDown

        result = MarkItDown().convert(path)
        return _clean_text(result.text_content)
    except Exception:
        return ""


def _ocr_pdf(path: Path) -> str:
    """OCR PDF scan bằng Poppler và Tesseract với mô hình tiếng Việt."""
    missing = [
        command
        for command in ("pdftoppm", "tesseract")
        if shutil.which(command) is None
    ]
    if missing:
        commands = ", ".join(missing)
        raise RuntimeError(
            f"PDF {path.name} không có text layer và thiếu công cụ OCR: {commands}. "
            "Cài tesseract-ocr, tesseract-ocr-vie và poppler-utils."
        )

    with tempfile.TemporaryDirectory(prefix="task3_ocr_") as temp_dir:
        image_prefix = Path(temp_dir) / "page"
        subprocess.run(
            [
                "pdftoppm",
                "-jpeg",
                "-r",
                "180",
                str(path),
                str(image_prefix),
            ],
            check=True,
            capture_output=True,
        )

        pages: list[str] = []
        for page_number, image_path in enumerate(
            sorted(Path(temp_dir).glob("page-*.jpg")),
            1,
        ):
            result = subprocess.run(
                [
                    "tesseract",
                    str(image_path),
                    "stdout",
                    "-l",
                    "vie+eng",
                    "--psm",
                    "6",
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            page_text = _clean_text(result.stdout)
            if page_text:
                pages.append(f"## Trang {page_number}\n\n{page_text}")

    content = "\n\n".join(pages)
    if len(content) < MIN_PDF_TEXT_LENGTH:
        raise ValueError(f"OCR không lấy đủ nội dung từ {path.name}")
    return content


def _convert_legal_document(path: Path) -> str:
    content = _convert_with_markitdown(path)
    if path.suffix.lower() == ".pdf" and len(content) < MIN_PDF_TEXT_LENGTH:
        print(f"PDF scan, đang OCR: {path.name}")
        content = _ocr_pdf(path)
    if len(content) < MIN_CONTENT_LENGTH:
        raise ValueError(f"Không trích xuất được nội dung từ {path.name}")
    return _clean_legal_markdown(content)


def convert_legal_docs() -> list[Path]:
    """Convert PDF/DOC/DOCX trong landing/legal sang Markdown."""
    legal_dir = LANDING_DIR / "legal"
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)
    source_paths = sorted(
        path
        for path in legal_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".pdf", ".doc", ".docx"}
    )
    if not source_paths:
        raise RuntimeError(f"Không có tài liệu pháp lý trong {legal_dir}")

    outputs: list[Path] = []
    for source in source_paths:
        output = output_dir / f"{source.stem}.md"
        if _is_fresh(source, output):
            print(f"Đã có: {output.relative_to(ROOT_DIR)}")
            outputs.append(output)
            continue

        metadata = LEGAL_METADATA.get(
            source.stem,
            {
                "title": source.stem.replace("_", " ").title(),
                "url": None,
                "transcription_url": None,
            },
        )
        body = _convert_legal_document(source)
        header = (
            f"# {metadata['title']}\n\n"
            f"**Source file:** {source.name}\n\n"
            f"**Source URL:** {metadata['url'] or 'Không có'}\n\n"
            + (
                f"**Text transcription:** {metadata['transcription_url']}\n\n"
                if metadata.get("transcription_url")
                else ""
            )
            + f"**Standardization:** {STANDARDIZATION_VERSION}\n\n"
            "---\n\n"
        )
        _write_atomic(output, header + body)
        print(f"Đã lưu: {output.relative_to(ROOT_DIR)}")
        outputs.append(output)
    return outputs


def _validate_news(data: object, source: Path) -> dict[str, str]:
    if not isinstance(data, dict):
        raise ValueError(f"{source.name} phải chứa một JSON object")
    required = ("url", "title", "date_crawled", "content_markdown")
    for field in required:
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise ValueError(f"{source.name} thiếu trường hợp lệ: {field}")
    if len(data["content_markdown"].strip()) < MIN_CONTENT_LENGTH:
        raise ValueError(f"Nội dung quá ngắn trong {source.name}")
    return data


def convert_news_articles() -> list[Path]:
    """Convert JSON trong landing/news sang Markdown có metadata."""
    news_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)
    source_paths = sorted(news_dir.glob("*.json"))
    if not source_paths:
        raise RuntimeError(f"Không có bài viết JSON trong {news_dir}")

    outputs: list[Path] = []
    for source in source_paths:
        output = output_dir / f"{source.stem}.md"
        if _is_fresh(source, output):
            print(f"Đã có: {output.relative_to(ROOT_DIR)}")
            outputs.append(output)
            continue

        try:
            raw_data = json.loads(source.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"JSON không hợp lệ: {source.name}") from error
        data = _validate_news(raw_data, source)
        body = _clean_news_markdown(
            data["content_markdown"],
            data["title"],
            data["url"],
        )
        markdown = (
            f"# {data['title']}\n\n"
            f"**Source:** {data['url']}\n\n"
            f"**Crawled:** {data['date_crawled']}\n\n"
            f"**Standardization:** {STANDARDIZATION_VERSION}\n\n"
            "---\n\n"
            f"{body}\n"
        )
        _write_atomic(output, markdown)
        print(f"Đã lưu: {output.relative_to(ROOT_DIR)}")
        outputs.append(output)
    return outputs


def convert_all() -> None:
    """Convert toàn bộ dữ liệu landing và xác nhận số lượng đầu ra."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    legal = convert_legal_docs()
    news = convert_news_articles()
    print(
        f"Hoàn tất: {len(legal)} tài liệu pháp lý và {len(news)} bài viết "
        f"tại {OUTPUT_DIR}"
    )


if __name__ == "__main__":
    convert_all()
