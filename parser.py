from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import ParseResult, urlparse

import requests
from bs4 import BeautifulSoup, Tag


# ----------------------------
# Настройки
# ----------------------------

REQUEST_TIMEOUT = (5, 20)  # connect timeout, read timeout
MIN_EXTRACTED_CHARS = 400

USER_AGENT = (
    "Mozilla/5.0 (compatible; AgreementTextExtractor/1.0; "
    "+https://example.com/bot-info)"
)

NOISY_TAGS = (
    "script",
    "style",
    "noscript",
    "svg",
    "canvas",
    "iframe",
    "form",
    "button",
    "input",
    "select",
    "textarea",
    "nav",
    "footer",
    "header",
    "aside",
)

BLOCK_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]

LEGAL_HINT_RE = re.compile(
    r"(terms?|conditions?|agreement|policy|privacy|legal|content|article|main|document)",
    re.IGNORECASE,
)

JUNK_ATTR_RE = re.compile(
    r"(cookie|banner|popup|modal|subscribe|newsletter|advert|ads|breadcrumb|sidebar|"
    r"menu|navigation|promo|social|share)",
    re.IGNORECASE,
)


# ----------------------------
# Исключения
# ----------------------------

class AgreementExtractorError(Exception):
    """Базовая ошибка извлекателя."""


class InvalidURLError(AgreementExtractorError):
    """URL пустой, некорректный или использует неподдерживаемую схему."""


class PageLoadError(AgreementExtractorError):
    """Страница не загрузилась или вернула неподходящий ответ."""


class ExtractionError(AgreementExtractorError):
    """Текст не удалось извлечь достаточно надёжно."""


class FileSaveError(AgreementExtractorError):
    """Ошибка при сохранении Markdown-файла."""


@dataclass(frozen=True)
class ExtractedDocument:
    title: str
    markdown: str
    char_count: int
    word_count: int


# ----------------------------
# URL и загрузка
# ----------------------------

def normalize_url(raw_url: str) -> tuple[str, ParseResult]:
    """
    Проверяет и нормализует URL.

    Если пользователь ввёл example.com/terms без схемы,
    автоматически добавляем https://.
    """
    raw_url = raw_url.strip()

    if not raw_url:
        raise InvalidURLError("URL не может быть пустым.")

    parsed = urlparse(raw_url)

    if not parsed.scheme:
        raw_url = f"https://{raw_url}"
        parsed = urlparse(raw_url)

    if parsed.scheme not in {"http", "https"}:
        raise InvalidURLError(
            f"Неподдерживаемая схема URL: {parsed.scheme!r}. Используйте http или https."
        )

    if not parsed.netloc:
        raise InvalidURLError("Некорректный URL: не найден домен сайта.")

    return raw_url, parsed


def fetch_html(url: str) -> str:
    """Загружает HTML страницы с обработкой типичных сетевых ошибок."""
    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()

    except requests.exceptions.Timeout as exc:
        raise PageLoadError("Истекло время ожидания ответа от сайта.") from exc

    except requests.exceptions.TooManyRedirects as exc:
        raise PageLoadError("Слишком много перенаправлений при загрузке страницы.") from exc

    except requests.exceptions.ConnectionError as exc:
        raise PageLoadError("Не удалось подключиться к сайту. Проверьте домен и сеть.") from exc

    except requests.exceptions.HTTPError as exc:
        status_code = getattr(exc.response, "status_code", "неизвестен")
        raise PageLoadError(f"Сайт вернул HTTP-ошибку: {status_code}.") from exc

    except requests.exceptions.RequestException as exc:
        raise PageLoadError(f"Ошибка при загрузке страницы: {exc}") from exc

    content_type = response.headers.get("Content-Type", "").lower()

    if content_type and (
        "text/html" not in content_type
        and "application/xhtml+xml" not in content_type
    ):
        raise PageLoadError(
            f"Страница вернула не HTML-контент: {content_type!r}."
        )

    if not response.text.strip():
        raise PageLoadError("Страница загрузилась, но HTML пустой.")

    return response.text


# ----------------------------
# Очистка и извлечение текста
# ----------------------------

def clean_spaces(text: str) -> str:
    """Схлопывает лишние пробелы и переносы строк."""
    return re.sub(r"\s+", " ", text).strip()


def get_attr_text(tag: Tag) -> str:
    """Собирает id/class/role тега в одну строку для эвристик."""
    parts: list[str] = []

    for attr_name in ("id", "class", "role", "aria-label"):
        value = tag.get(attr_name)

        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif value:
            parts.append(str(value))

    return " ".join(parts).lower()


def remove_noisy_html(soup: BeautifulSoup) -> None:
    """Удаляет блоки, которые почти никогда не относятся к основному тексту."""
    for tag in soup.find_all(NOISY_TAGS):
        tag.decompose()

    for tag in soup.select(
        '[role="navigation"], '
        '[role="banner"], '
        '[role="contentinfo"], '
        '[aria-hidden="true"]'
    ):
        tag.decompose()

    # Удаляем рекламные, cookie, modal, sidebar и похожие блоки по id/class/role.
    for tag in list(soup.find_all(True)):
        if not isinstance(tag, Tag):
            continue

        attr_text = get_attr_text(tag)

        if JUNK_ATTR_RE.search(attr_text) and not LEGAL_HINT_RE.search(attr_text):
            tag.decompose()


def score_container(tag: Tag) -> int:
    """
    Оценивает, насколько тег похож на основной контейнер соглашения.

    Чем больше текста, абзацев и юридических подсказок в class/id,
    и чем меньше доля ссылочного текста, тем выше оценка.
    """
    text = clean_spaces(tag.get_text(" ", strip=True))
    text_len = len(text)

    if text_len < 200:
        return -1

    links_text_len = sum(
        len(clean_spaces(link.get_text(" ", strip=True)))
        for link in tag.find_all("a")
    )

    link_ratio = links_text_len / max(text_len, 1)

    heading_count = len(tag.find_all(re.compile(r"^h[1-6]$")))
    paragraph_count = len(tag.find_all(["p", "li"]))

    score = text_len
    score += min(heading_count, 20) * 80
    score += min(paragraph_count, 80) * 25

    if tag.name in {"main", "article"}:
        score += 1000

    if tag.get("role") == "main":
        score += 1000

    if LEGAL_HINT_RE.search(get_attr_text(tag)):
        score += 700

    # Навигационные и индексные блоки часто состоят преимущественно из ссылок.
    score -= int(text_len * link_ratio * 1.5)

    return score


def choose_main_container(soup: BeautifulSoup) -> Tag:
    """Выбирает наиболее вероятный контейнер с основным текстом."""
    candidates: list[Tag] = []

    for tag in soup.find_all(["main", "article", "section", "div"]):
        if isinstance(tag, Tag):
            candidates.append(tag)

    if soup.body:
        candidates.append(soup.body)

    if not candidates:
        raise ExtractionError("В HTML не найден body или подходящие текстовые контейнеры.")

    best = max(candidates, key=score_container)

    if score_container(best) < 0:
        raise ExtractionError("Не удалось найти достаточно крупный текстовый блок.")

    return best


def has_allowed_block_parent(tag: Tag, root: Tag) -> bool:
    """
    Проверяет, находится ли тег внутри другого блочного тега,
    который уже будет обработан. Это помогает избежать дублей.
    """
    parent = tag.parent

    while isinstance(parent, Tag) and parent is not root:
        if parent.name in BLOCK_TAGS:
            return True
        parent = parent.parent

    return False


def block_to_markdown(tag: Tag) -> str | None:
    """Конвертирует отдельный HTML-блок в Markdown."""
    text = clean_spaces(tag.get_text(" ", strip=True))

    if not text:
        return None

    if tag.name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        level = int(tag.name[1])
        return f"{'#' * level} {text}"

    if tag.name == "li":
        return f"- {text}"

    return text


def container_to_markdown(container: Tag) -> str:
    """
    Извлекает заголовки, абзацы и элементы списков
    в порядке их появления на странице.
    """
    blocks: list[str] = []
    previous_normalized = ""

    for tag in container.find_all(BLOCK_TAGS):
        if not isinstance(tag, Tag):
            continue

        if has_allowed_block_parent(tag, container):
            continue

        block = block_to_markdown(tag)

        if not block:
            continue

        # Убираем подряд идущие дубли.
        normalized = re.sub(r"^[#\-\s]+", "", block).lower()

        if normalized == previous_normalized:
            continue

        blocks.append(block)
        previous_normalized = normalized

    if not blocks:
        fallback_text = clean_spaces(container.get_text(" ", strip=True))

        if fallback_text:
            blocks.append(fallback_text)

    return "\n\n".join(blocks).strip()


def extract_document(html: str, source_url: str) -> ExtractedDocument:
    """Главная функция извлечения текста соглашения."""
    soup = BeautifulSoup(html, "html.parser")

    title = ""
    if soup.title and soup.title.string:
        title = clean_spaces(soup.title.string)

    remove_noisy_html(soup)

    container = choose_main_container(soup)
    body_markdown = container_to_markdown(container)

    plain_text = clean_spaces(container.get_text(" ", strip=True))
    char_count = len(plain_text)
    word_count = len(plain_text.split())

    if char_count < MIN_EXTRACTED_CHARS:
        raise ExtractionError(
            "Извлечённый текст слишком короткий. "
            "Возможно, страница рендерится JavaScript-ом, закрыта баннером "
            "или имеет нестандартную структуру."
        )

    today = date.today().isoformat()

    markdown_parts: list[str] = []

    if title:
        markdown_parts.append(f"# {title}")
    else:
        markdown_parts.append("# Extracted user agreement")

    markdown_parts.append(f"_Source: {source_url}_")
    markdown_parts.append(f"_Retrieved: {today}_")

    # Если первый найденный h1 совпадает с title, не дублируем его.
    if title:
        first_block_normalized = ""
        body_blocks = body_markdown.split("\n\n")

        if body_blocks:
            first_block_normalized = re.sub(
                r"^[#\-\s]+",
                "",
                body_blocks[0],
            ).strip().lower()

        if first_block_normalized == title.lower():
            body_markdown = "\n\n".join(body_blocks[1:]).strip()

    if body_markdown:
        markdown_parts.append(body_markdown)

    final_markdown = "\n\n".join(markdown_parts).strip() + "\n"

    return ExtractedDocument(
        title=title,
        markdown=final_markdown,
        char_count=char_count,
        word_count=word_count,
    )


# ----------------------------
# Сохранение файла
# ----------------------------

def domain_to_slug(parsed_url: ParseResult) -> str:
    """Преобразует домен в безопасную часть имени файла."""
    host = parsed_url.hostname or parsed_url.netloc

    if host.startswith("www."):
        host = host[4:]

    slug = re.sub(r"[^a-zA-Z0-9]+", "-", host.lower()).strip("-")

    return slug or "site"


def build_output_path(parsed_url: ParseResult) -> Path:
    """
    Формирует имя файла site-name_YYYY-MM-DD.md.

    Если такой файл уже есть, добавляет числовой суффикс,
    чтобы случайно не перезаписать предыдущий результат.
    """
    slug = domain_to_slug(parsed_url)
    today = date.today().isoformat()

    base_path = Path(f"{slug}_{today}.md")

    if not base_path.exists():
        return base_path

    counter = 2

    while True:
        candidate = Path(f"{slug}_{today}_{counter}.md")

        if not candidate.exists():
            return candidate

        counter += 1


def save_markdown(markdown: str, parsed_url: ParseResult) -> Path:
    """Сохраняет Markdown в файл рядом со скриптом."""
    output_path = build_output_path(parsed_url)

    try:
        output_path.write_text(markdown, encoding="utf-8")
    except OSError as exc:
        raise FileSaveError(f"Не удалось записать файл {output_path}: {exc}") from exc

    return output_path


# ----------------------------
# Точка входа
# ----------------------------

def main() -> int:
    raw_url = input("Введите URL страницы пользовательского соглашения: ")

    try:
        url, parsed_url = normalize_url(raw_url)
        html = fetch_html(url)
        document = extract_document(html, url)
        output_path = save_markdown(document.markdown, parsed_url)

    except AgreementExtractorError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1

    except KeyboardInterrupt:
        print("\nОперация отменена пользователем.", file=sys.stderr)
        return 130

    print("Готово.")
    print(f"Файл сохранён: {output_path.resolve()}")
    print(f"Извлечено символов: {document.char_count}")
    print(f"Извлечено слов: {document.word_count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())