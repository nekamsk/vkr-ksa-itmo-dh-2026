#!/usr/bin/env python3
"""
Скрипт для конвертации всех PDF-файлов в указанной директории в Markdown
с помощью библиотеки docling и настройкой PdfPipelineOptions (queue_max_size=5).
"""

import sys
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption


def convert_all_pdfs(directory: str = ".") -> None:
    """
    Находит все PDF-файлы в заданной директории, конвертирует их в Markdown
    и сохраняет рядом с оригиналом с расширением .md.
    """

    input_dir = Path(directory).resolve()
    if not input_dir.is_dir():
        print(f"Ошибка: '{directory}' не является директорией.")
        sys.exit(1)

    pdf_files = list(input_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"В директории '{input_dir}' не найдено PDF-файлов.")
        return

    print(f"Найдено {len(pdf_files)} PDF-файлов. Запуск конвертации...")

    # Настройка опций для обработки PDF
    pipeline_options = PdfPipelineOptions(
        queue_max_size=5,    # обязательный параметр по заданию
        # при необходимости здесь можно добавить другие опции,
        # например, artifacts_path, enable_remote_services и т.д.
    )

    # Конфигурация формата PDF с указанными опциями
    pdf_format_option = PdfFormatOption(pipeline_options=pipeline_options)

    # Создаём конвертер, передавая настройки для входного формата PDF
    converter = DocumentConverter(
        format_options={InputFormat.PDF: pdf_format_option}
    )

    for pdf_path in pdf_files:
        md_path = pdf_path.with_suffix(".md")
        print(f"Конвертация {pdf_path.name} -> {md_path.name} ...", end=" ", flush=True)

        try:
            result = converter.convert(str(pdf_path))
            markdown_text = result.document.export_to_markdown()

            md_path.write_text(markdown_text, encoding="utf-8")
            print("успешно")
        except Exception as e:
            print(f"ошибка: {e}")


if __name__ == "__main__":
    # Если передан аргумент командной строки, используем его как путь к директории,
    # иначе обрабатываем текущую папку.
    if len(sys.argv) > 1:
        target_dir = sys.argv[1]
    else:
        target_dir = "."

    convert_all_pdfs(target_dir)