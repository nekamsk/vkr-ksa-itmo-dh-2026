#!/usr/bin/env python3
"""
Замена пробелов на '_' в именах файлов в директории этого скрипта.
Запустите скрипт, и все файлы (по умолчанию) в его папке будут переименованы.
"""

import os
import sys
from pathlib import Path

# Если нужно обрабатывать и папки, раскомментируйте строку ниже
RENAME_DIRS = False


def replace_spaces_in_filename(file_path: Path) -> bool:
    """Переименовывает файл, заменяя пробелы в имени на '_'."""
    old_name = file_path.name
    new_name = old_name.replace(' ', '_')

    if old_name == new_name:
        return False

    new_path = file_path.with_name(new_name)

    if new_path.exists():
        print(f"Пропущен '{file_path}': целевое имя уже существует",
              file=sys.stderr)
        return False

    try:
        os.rename(file_path, new_path)
        print(f"Переименован: '{file_path.name}' -> '{new_name}'")
        return True
    except OSError as e:
        print(f"Ошибка переименования '{file_path}': {e}", file=sys.stderr)
        return False


def main():
    # Директория, в которой находится этот скрипт
    script_dir = Path(__file__).resolve().parent
    print(f"Работаем в директории: {script_dir}")

    # Сбор всех файлов (и, опционально, папок)
    try:
        entries = list(script_dir.iterdir())
    except PermissionError as e:
        print(f"Нет доступа к директории: {e}", file=sys.stderr)
        sys.exit(1)

    # Отделяем файлы и папки (если нужно)
    if RENAME_DIRS:
        targets = entries  # всё подряд
    else:
        targets = [e for e in entries if e.is_file()]

    # Исключаем сам скрипт, чтобы не переименовать его случайно
    this_script = Path(__file__).resolve()
    targets = [t for t in targets if t.resolve() != this_script]

    success = 0
    for target in targets:
        if replace_spaces_in_filename(target):
            success += 1

    print(f"\nГотово. Успешно переименовано: {success} элементов.")


if __name__ == '__main__':
    main()