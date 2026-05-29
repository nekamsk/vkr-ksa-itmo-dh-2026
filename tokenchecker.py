#!/usr/bin/env python3
"""
Скрипт для оценки количества токенов в Markdown-файлах директории.
Поддерживает два режима:
  - приблизительный: токены = ceil(число_символов / 4)
  - точный: через tiktoken (модель gpt-5.5 / o200k_base)
"""

import argparse
import math
from pathlib import Path
from typing import Tuple

# Кодировка по умолчанию для моделей GPT-5.5 и других современных моделей OpenAI
DEFAULT_ENCODING = "o200k_base"

def count_tokens_approximate(text: str) -> int:
    """
    Грубая оценка числа токенов по количеству символов.
    Среднее соотношение для английского текста: 1 токен ~ 4 символа.
    Для кириллицы и других языков коэффициент может отличаться.
    """
    return math.ceil(len(text) / 4)

def count_tokens_tiktoken(text: str, encoding_name: str = DEFAULT_ENCODING) -> int:
    """
    Точный подсчёт токенов с помощью tiktoken.
    Подходит для моделей GPT-5.5, GPT-5, GPT-4.1, GPT-4o, o4, o3, o1.
    """
    import tiktoken
    encoding = tiktoken.get_encoding(encoding_name)
    return len(encoding.encode(text))

def collect_md_content(directory: Path) -> Tuple[int, int]:
    """
    Рекурсивно обходит directory, собирает содержимое всех .md файлов.
    Возвращает (общее_количество_символов, количество_файлов).
    """
    total_chars = 0
    file_count = 0

    for md_file in directory.rglob("*.md"):
        if md_file.is_file():
            try:
                content = md_file.read_text(encoding="utf-8")
                total_chars += len(content)
                file_count += 1
            except Exception as e:
                print(f"⚠️  Пропущен файл {md_file}: {e}")

    return total_chars, file_count

def estimate_tokens(
    directory: str, 
    threshold: int = 32_000, 
    use_tiktoken: bool = False, 
    encoding_name: str = DEFAULT_ENCODING
) -> None:
    """
    Основная логика: сбор файлов, подсчёт токенов, вывод результата и предупреждения.
    """
    dir_path = Path(directory).expanduser().resolve()
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Указанный путь не является директорией: {dir_path}")

    total_chars, file_count = collect_md_content(dir_path)

    if file_count == 0:
        print("ℹ️  В директории не найдено .md файлов.")
        return

    # Выбор метода подсчёта
    if use_tiktoken:
        try:
            # Для точного подсчёта нужно прочитать все файлы
            all_text = ""
            for md_file in dir_path.rglob("*.md"):
                if md_file.is_file():
                    all_text += md_file.read_text(encoding="utf-8")
            total_tokens = count_tokens_tiktoken(all_text, encoding_name)
            method = f"tiktoken ({encoding_name})"
        except ImportError:
            print("❌ Библиотека tiktoken не установлена. Использую приблизительный метод.")
            total_tokens = math.ceil(total_chars / 4)
            method = "приблизительный (символы / 4)"
        except Exception as e:
            print(f"❌ Ошибка при точном подсчёте токенов: {e}. Использую приблизительный метод.")
            total_tokens = math.ceil(total_chars / 4)
            method = "приблизительный (символы / 4)"
    else:
        total_tokens = math.ceil(total_chars / 4)
        method = "приблизительный (символы / 4)"

    # Вывод статистики
    print(f"📁 Директория: {dir_path}")
    print(f"📄 Найдено .md файлов: {file_count}")
    print(f"🔤 Общее количество символов: {total_chars:,}")
    print(f"🧮 Метод подсчёта токенов: {method}")
    print(f"🎯 Оценка количества токенов: {total_tokens:,}")

    # Проверка порога
    if total_tokens > threshold:
        print(f"⚠️  ВНИМАНИЕ: Количество токенов ({total_tokens:,}) превышает порог в {threshold:,}!")
    else:
        print(f"✅ Количество токенов в пределах допустимого порога ({threshold:,}).")

def main():
    parser = argparse.ArgumentParser(
        description="Подсчёт токенов в Markdown-файлах директории"
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Путь к директории с .md файлами (по умолчанию текущая)",
    )
    parser.add_argument(
        "-t", "--threshold",
        type=int,
        default=32_000,
        help="Порог количества токенов для предупреждения (по умолчанию 32000)",
    )
    parser.add_argument(
        "--tiktoken",
        action="store_true",
        help="Использовать tiktoken для точного подсчёта (требуется установка)",
    )
    parser.add_argument(
        "--encoding",
        type=str,
        default=DEFAULT_ENCODING,
        help=f"Название кодировки для точного подсчёта (по умолчанию: {DEFAULT_ENCODING})",
    )
    args = parser.parse_args()

    try:
        estimate_tokens(args.directory, args.threshold, args.tiktoken, args.encoding)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        raise SystemExit(1)

if __name__ == "__main__":
    main()