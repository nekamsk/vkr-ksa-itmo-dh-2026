#!/usr/bin/env python3
"""
Конвертация PDF и DOCX файлов в Markdown с помощью docling.
Для PDF обязательно используется PdfPipelineOptions (queue_max_size=5).
"""

import sys
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption


def convert_all_pdfs_and_docx(directory: str = ".") -> None:
    """
    Находит PDF и DOCX в указанной директории, конвертирует в Markdown
    и сохраняет с расширением .md.
    """
    input_dir = Path(directory).resolve()
    if not input_dir.is_dir():
        print(f"Ошибка: '{directory}' не является директорией.")
        sys.exit(1)

    # Собираем оба типа файлов
    pdf_files = list(input_dir.glob("*.pdf"))
    docx_files = list(input_dir.glob("*.docx"))
    all_files = pdf_files + docx_files

    if not all_files:
        print(f"В '{input_dir}' нет PDF или DOCX файлов.")
        return

    print(f"Найдено {len(pdf_files)} PDF + {len(docx_files)} DOCX. Запуск конвертации...")

    # Настройка PDF с обязательным параметром
    pdf_pipeline = PdfPipelineOptions(queue_max_size=5)
    pdf_format = PdfFormatOption(pipeline_options=pdf_pipeline)

    # Конвертер сразу со всеми форматами
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: pdf_format,
            # DOCX обрабатывается автоматически, дополнительные опции не обязательны
        }
    )

    for src_path in all_files:
        md_path = src_path.with_suffix(".md")
        print(f"Конвертация {src_path.name} -> {md_path.name} ...", end=" ", flush=True)

        try:
            result = converter.convert(str(src_path))
            markdown_text = result.document.export_to_markdown()
            md_path.write_text(markdown_text, encoding="utf-8")
            print("успешно")
        except Exception as e:
            print(f"ошибка: {e}")


if __name__ == "__main__":
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    convert_all_pdfs_and_docx(target_dir)