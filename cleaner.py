from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from datetime import datetime
import argparse
import hashlib
import logging
import os
import re
import sys
import traceback


try:
    from rapidfuzz import fuzz
except ModuleNotFoundError:
    print("КРИТИЧЕСКАЯ ОШИБКА: не установлена библиотека rapidfuzz.")
    print("Установи её командой:")
    print("pip install rapidfuzz")
    sys.exit(1)


SIMILARITY_THRESHOLD = 0.90
LOG_FILENAME = "clean.md"


@dataclass(frozen=True)
class CleanerConfig:
    base_dir: Path
    target_dir: Path
    log_path: Path
    delete_enabled: bool
    cpu_workers: int
    io_workers: int
    threshold: float = SIMILARITY_THRESHOLD
    gpu_prefilter: bool = False
    simhash_max_distance: int = 24
    verbose: bool = False


@dataclass(frozen=True)
class FileMeta:
    path: Path
    size: int
    sha256: str
    first_line: str
    simhash: int | None = None


@dataclass(frozen=True)
class PairResult:
    left: Path
    right: Path
    ratio: float
    method: str


@dataclass(frozen=True)
class DuplicateRecord:
    deleted_file: Path
    original_file: Path
    size: int
    similarity: float
    method: str
    deleted_first_line: str
    original_first_line: str
    actually_deleted: bool


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def script_directory() -> Path:
    return Path(__file__).resolve().parent


def is_inside_directory(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def extract_first_line(raw: bytes) -> str:
    lines = raw.splitlines()
    if not lines:
        return ""
    return lines[0].decode("utf-8", errors="replace").strip()


def compare_pair_worker(args: tuple[str, str, float]) -> tuple[str, str, float]:
    """
    Worker для ProcessPoolExecutor.

    Важно: передаём пути, а не огромные строки.
    Каждый процесс сам читает файлы. ОС обычно кеширует повторное чтение.
    """
    left_path_raw, right_path_raw, threshold = args

    left_path = Path(left_path_raw)
    right_path = Path(right_path_raw)

    left_text = left_path.read_text(encoding="utf-8", errors="replace")
    right_text = right_path.read_text(encoding="utf-8", errors="replace")

    if left_text == right_text:
        return left_path_raw, right_path_raw, 1.0

    score = fuzz.ratio(
        left_text,
        right_text,
        score_cutoff=threshold * 100,
    )

    return left_path_raw, right_path_raw, score / 100


class SimHasher:
    """
    Быстрый SimHash по токенам.

    Это не финальная метрика удаления.
    SimHash нужен только для предварительного отсечения явно разных пар.
    """

    TOKEN_RE = re.compile(r"\S+")

    @classmethod
    def compute(cls, text: str) -> int:
        vector = [0] * 64

        for token in cls.TOKEN_RE.findall(text.casefold()):
            digest = hashlib.blake2b(
                token.encode("utf-8", errors="ignore"),
                digest_size=8,
            ).digest()

            value = int.from_bytes(digest, byteorder="little", signed=False)

            for bit in range(64):
                if value & (1 << bit):
                    vector[bit] += 1
                else:
                    vector[bit] -= 1

        result = 0

        for bit, weight in enumerate(vector):
            if weight >= 0:
                result |= 1 << bit

        return result


class MarkdownScanner:
    def __init__(self, config: CleanerConfig) -> None:
        self.config = config

    def collect(self) -> list[Path]:
        root = self.config.target_dir
        log_path = self.config.log_path

        logging.info(f"Начинаю поиск .md файлов внутри: {root}")

        files: list[Path] = []
        scanned_count = 0

        for path in root.rglob("*.md"):
            scanned_count += 1

            try:
                if path.is_symlink():
                    logging.warning(f"Пропущена символическая ссылка: {path}")
                    continue

                if not path.is_file():
                    continue

                resolved_path = path.resolve()

                if not is_inside_directory(resolved_path, root):
                    logging.warning(f"Пропущен файл вне рабочей директории: {path}")
                    continue

                if path.name.lower() == LOG_FILENAME.lower():
                    continue

                if resolved_path == log_path.resolve():
                    continue

                files.append(path)

                if self.config.verbose:
                    logging.debug(f"Файл добавлен в обработку: {path}")

            except Exception as exc:
                logging.error(f"Ошибка при проверке файла {path}: {exc}")

        files = sorted(files)

        logging.info(f"Всего найдено .md кандидатов: {scanned_count}")
        logging.info(f"Всего добавлено в обработку: {len(files)}")

        return files


class FileGrouper:
    @staticmethod
    def by_size(paths: list[Path]) -> dict[int, list[Path]]:
        grouped: dict[int, list[Path]] = defaultdict(list)

        total = len(paths)
        logging.info("Группирую файлы по размеру в байтах.")

        for index, path in enumerate(paths, start=1):
            try:
                size = path.stat().st_size
                grouped[size].append(path)

                logging.info(
                    f"Проверка размера {index} из {total}: "
                    f"{size} байт | {path}"
                )

            except FileNotFoundError:
                logging.warning(f"Файл исчез до проверки размера: {path}")

            except Exception as exc:
                logging.error(f"Ошибка при получении размера {path}: {exc}")

        return dict(grouped)


class FileMetaLoader:
    def __init__(self, config: CleanerConfig) -> None:
        self.config = config

    def load_one(self, path: Path) -> FileMeta:
        raw = path.read_bytes()

        sha256 = hashlib.sha256(raw).hexdigest()
        first_line = extract_first_line(raw)

        simhash: int | None = None

        if self.config.gpu_prefilter:
            text = raw.decode("utf-8", errors="replace")
            simhash = SimHasher.compute(text)

        return FileMeta(
            path=path,
            size=len(raw),
            sha256=sha256,
            first_line=first_line,
            simhash=simhash,
        )

    def load_group(
        self,
        paths: list[Path],
        group_index: int,
        groups_total: int,
    ) -> list[FileMeta]:
        total = len(paths)

        logging.info(
            f"Загружаю метаданные группы {group_index} из {groups_total}. "
            f"Файлов: {total}. IO-потоков: {self.config.io_workers}"
        )

        metas: list[FileMeta] = []

        with ThreadPoolExecutor(max_workers=self.config.io_workers) as executor:
            futures = {
                executor.submit(self.load_one, path): path
                for path in paths
            }

            for index, future in enumerate(as_completed(futures), start=1):
                path = futures[future]

                try:
                    meta = future.result()
                    metas.append(meta)

                    logging.info(
                        f"Загружен подозрительный файл "
                        f"{index} из {total}: {path}"
                    )

                except FileNotFoundError:
                    logging.warning(f"Файл исчез до чтения: {path}")

                except Exception as exc:
                    logging.error(f"Ошибка при загрузке файла {path}: {exc}")

        return sorted(metas, key=lambda item: str(item.path).casefold())


class CudaSimhashPrefilter:
    def __init__(self, config: CleanerConfig) -> None:
        self.config = config

    def filter_pairs(
        self,
        pairs: list[tuple[FileMeta, FileMeta]],
    ) -> list[tuple[FileMeta, FileMeta]]:
        if not self.config.gpu_prefilter:
            return pairs

        if not pairs:
            return pairs

        if any(left.simhash is None or right.simhash is None for left, right in pairs):
            logging.warning("SimHash отсутствует у части файлов. GPU-фильтр пропущен.")
            return pairs

        logging.info(
            f"Запускаю CUDA SimHash prefilter. "
            f"Пар до фильтра: {len(pairs)}. "
            f"Максимальная Hamming-дистанция: {self.config.simhash_max_distance}"
        )

        try:
            import cupy as cp

            left_hashes = cp.asarray(
                [left.simhash for left, _ in pairs],
                dtype=cp.uint64,
            )

            right_hashes = cp.asarray(
                [right.simhash for _, right in pairs],
                dtype=cp.uint64,
            )

            xor_values = cp.bitwise_xor(left_hashes, right_hashes)

            byte_view = xor_values.view(cp.uint8).reshape((-1, 8))

            popcount_table = cp.asarray(
                [bin(i).count("1") for i in range(256)],
                dtype=cp.uint8,
            )

            distances = popcount_table[byte_view].sum(axis=1)

            mask = cp.asnumpy(
                distances <= self.config.simhash_max_distance
            )

            filtered = [
                pair
                for pair, keep in zip(pairs, mask)
                if bool(keep)
            ]

            logging.info(
                f"CUDA SimHash prefilter завершён. "
                f"Пар после фильтра: {len(filtered)} из {len(pairs)}"
            )

            return filtered

        except ModuleNotFoundError:
            logging.warning(
                "CuPy не установлен. Перехожу на CPU SimHash prefilter. "
                "Для CUDA-режима установи подходящий cupy-пакет."
            )
            return self._cpu_filter_pairs(pairs)

        except Exception as exc:
            logging.warning(
                f"CUDA SimHash prefilter не сработал: {exc}. "
                f"Перехожу на CPU SimHash prefilter."
            )
            return self._cpu_filter_pairs(pairs)

    def _cpu_filter_pairs(
        self,
        pairs: list[tuple[FileMeta, FileMeta]],
    ) -> list[tuple[FileMeta, FileMeta]]:
        filtered: list[tuple[FileMeta, FileMeta]] = []

        for left, right in pairs:
            assert left.simhash is not None
            assert right.simhash is not None

            distance = (left.simhash ^ right.simhash).bit_count()

            if distance <= self.config.simhash_max_distance:
                filtered.append((left, right))

        logging.info(
            f"CPU SimHash prefilter завершён. "
            f"Пар после фильтра: {len(filtered)} из {len(pairs)}"
        )

        return filtered


class PairPlanner:
    @staticmethod
    def split_exact_and_fuzzy_candidates(
        metas: list[FileMeta],
    ) -> tuple[
        list[FileMeta],
        dict[tuple[Path, Path], PairResult],
    ]:
        """
        Отделяет полные SHA-256 дубли от файлов, которые нужно сравнивать через RapidFuzz.

        Возвращает:
        - представителей уникальных SHA-256;
        - уже найденные exact-pair результаты.
        """
        seen_by_hash: dict[str, FileMeta] = {}
        representatives: list[FileMeta] = []
        exact_results: dict[tuple[Path, Path], PairResult] = {}

        for meta in metas:
            original = seen_by_hash.get(meta.sha256)

            if original is None:
                seen_by_hash[meta.sha256] = meta
                representatives.append(meta)
                continue

            key = PairPlanner._pair_key(original.path, meta.path)

            exact_results[key] = PairResult(
                left=original.path,
                right=meta.path,
                ratio=1.0,
                method="SHA-256 exact match",
            )

        return representatives, exact_results

    @staticmethod
    def build_pairs(metas: list[FileMeta]) -> list[tuple[FileMeta, FileMeta]]:
        pairs: list[tuple[FileMeta, FileMeta]] = []

        for i in range(len(metas)):
            for j in range(i + 1, len(metas)):
                pairs.append((metas[i], metas[j]))

        return pairs

    @staticmethod
    def _pair_key(left: Path, right: Path) -> tuple[Path, Path]:
        ordered = sorted([left, right], key=lambda item: str(item).casefold())
        return ordered[0], ordered[1]


class RapidFuzzComparator:
    def __init__(self, config: CleanerConfig) -> None:
        self.config = config

    def compare_pairs(
        self,
        pairs: list[tuple[FileMeta, FileMeta]],
    ) -> dict[tuple[Path, Path], PairResult]:
        results: dict[tuple[Path, Path], PairResult] = {}

        if not pairs:
            logging.info("Нет пар для RapidFuzz-сравнения.")
            return results

        total = len(pairs)

        logging.info(
            f"Начинаю RapidFuzz-сравнение. "
            f"Пар: {total}. CPU-процессов: {self.config.cpu_workers}"
        )

        worker_args = [
            (
                str(left.path),
                str(right.path),
                self.config.threshold,
            )
            for left, right in pairs
        ]

        with ProcessPoolExecutor(max_workers=self.config.cpu_workers) as executor:
            futures = {
                executor.submit(compare_pair_worker, args): args
                for args in worker_args
            }

            for completed, future in enumerate(as_completed(futures), start=1):
                left_raw, right_raw, _ = futures[future]

                logging.info(
                    f"Сравнивается пара {completed} из {total}: "
                    f"{left_raw} <-> {right_raw}"
                )

                try:
                    left_path_raw, right_path_raw, ratio = future.result()

                    left_path = Path(left_path_raw)
                    right_path = Path(right_path_raw)

                    key = PairPlanner._pair_key(left_path, right_path)

                    results[key] = PairResult(
                        left=key[0],
                        right=key[1],
                        ratio=ratio,
                        method="RapidFuzz fuzz.ratio",
                    )

                    logging.info(
                        f"RapidFuzz результат пары {completed} из {total}: "
                        f"{ratio * 100:.2f}%"
                    )

                except FileNotFoundError as exc:
                    logging.warning(
                        f"Файл исчез во время RapidFuzz-сравнения: {exc}"
                    )

                except Exception as exc:
                    logging.error(
                        f"Ошибка RapidFuzz-сравнения пары "
                        f"{left_raw} <-> {right_raw}: {exc}"
                    )

        return results


class DuplicateResolver:
    def __init__(self, config: CleanerConfig) -> None:
        self.config = config

    def resolve(
        self,
        metas: list[FileMeta],
        pair_results: dict[tuple[Path, Path], PairResult],
    ) -> list[DuplicateRecord]:
        """
        Выбирает, какие файлы считать дубликатами.

        Правило:
        - файлы отсортированы по пути;
        - более ранний файл остаётся;
        - более поздний удаляется, если он напрямую совпал с одним из предыдущих.
        """
        meta_by_path = {meta.path: meta for meta in metas}
        ordered_paths = sorted(meta_by_path, key=lambda item: str(item).casefold())

        records: list[DuplicateRecord] = []

        for current_index, current_path in enumerate(ordered_paths):
            current_meta = meta_by_path[current_path]

            for original_path in ordered_paths[:current_index]:
                key = PairPlanner._pair_key(original_path, current_path)
                result = pair_results.get(key)

                if result is None:
                    continue

                if result.ratio > self.config.threshold:
                    original_meta = meta_by_path[original_path]

                    records.append(
                        DuplicateRecord(
                            deleted_file=current_meta.path,
                            original_file=original_meta.path,
                            size=current_meta.size,
                            similarity=result.ratio,
                            method=result.method,
                            deleted_first_line=current_meta.first_line,
                            original_first_line=original_meta.first_line,
                            actually_deleted=self.config.delete_enabled,
                        )
                    )

                    break

        return records


class FileDeleter:
    def __init__(self, config: CleanerConfig) -> None:
        self.config = config

    def delete_records(self, records: list[DuplicateRecord]) -> None:
        if not self.config.delete_enabled:
            logging.info("Удаление отключено. Файлы не удаляются.")
            return

        deleted_paths: set[Path] = set()

        for record in records:
            path = record.deleted_file.resolve()

            if path in deleted_paths:
                continue

            if not is_inside_directory(path, self.config.base_dir):
                raise ValueError(
                    f"Попытка удалить файл вне папки скрипта запрещена: {path}"
                )

            if path.name.lower() == LOG_FILENAME.lower():
                raise ValueError(f"Попытка удалить clean.md запрещена: {path}")

            if not path.exists():
                logging.warning(f"Файл уже отсутствует, пропускаю удаление: {path}")
                continue

            logging.warning(f"Удаляю файл: {path}")
            path.unlink()
            deleted_paths.add(path)
            logging.warning(f"Файл удалён: {path}")


class MarkdownReportWriter:
    def __init__(self, config: CleanerConfig) -> None:
        self.config = config

    def write(
        self,
        records: list[DuplicateRecord],
        suspicious_files_total: int,
        pair_comparisons_total: int,
        pair_comparisons_done: int,
    ) -> None:
        path = self.config.log_path

        logging.info(f"Записываю markdown-лог: {path}")

        with path.open("w", encoding="utf-8") as log:
            log.write("# clean.md\n\n")
            log.write(f"Дата запуска: `{datetime.now().isoformat(timespec='seconds')}`\n\n")
            log.write(f"Папка скрипта: `{self.config.base_dir}`\n\n")
            log.write(f"Проверенная папка: `{self.config.target_dir}`\n\n")
            log.write(f"Порог сходства: `{self.config.threshold * 100:.0f}%`\n\n")
            log.write(f"Реальное удаление: `{self.config.delete_enabled}`\n\n")
            log.write(f"CPU-процессы RapidFuzz: `{self.config.cpu_workers}`\n\n")
            log.write(f"IO-потоки: `{self.config.io_workers}`\n\n")
            log.write(f"CUDA SimHash prefilter: `{self.config.gpu_prefilter}`\n\n")
            log.write(f"SimHash max distance: `{self.config.simhash_max_distance}`\n\n")
            log.write(f"Подозрительных файлов: `{suspicious_files_total}`\n\n")
            log.write(f"Запланировано парных сравнений: `{pair_comparisons_total}`\n\n")
            log.write(f"Выполнено RapidFuzz-сравнений: `{pair_comparisons_done}`\n\n")

            if not records:
                log.write("Удалённых файлов нет.\n")
                return

            log.write("## Найденные дубликаты\n\n")

            for index, record in enumerate(records, start=1):
                status = "Удалён" if record.actually_deleted else "Был бы удалён"

                log.write(f"### {index}. {status}: `{record.deleted_file}`\n\n")
                log.write(f"- Оставлен файл: `{record.original_file}`\n")
                log.write(f"- Размер: `{record.size}` байт\n")
                log.write(f"- Сходство: `{record.similarity * 100:.2f}%`\n")
                log.write(f"- Метод: `{record.method}`\n")
                log.write(f"- Первая строка удаляемого файла: `{record.deleted_first_line}`\n")
                log.write(f"- Первая строка оставленного файла: `{record.original_first_line}`\n\n")


class DuplicateCleanerApp:
    def __init__(self, config: CleanerConfig) -> None:
        self.config = config
        self.scanner = MarkdownScanner(config)
        self.loader = FileMetaLoader(config)
        self.gpu_filter = CudaSimhashPrefilter(config)
        self.comparator = RapidFuzzComparator(config)
        self.resolver = DuplicateResolver(config)
        self.deleter = FileDeleter(config)
        self.report_writer = MarkdownReportWriter(config)

    def run(self) -> None:
        self._validate_paths()

        md_files = self.scanner.collect()
        grouped_by_size = FileGrouper.by_size(md_files)

        duplicate_size_groups = {
            size: paths
            for size, paths in grouped_by_size.items()
            if len(paths) > 1
        }

        suspicious_files_total = sum(
            len(paths)
            for paths in duplicate_size_groups.values()
        )

        logging.info(f"Всего групп размеров: {len(grouped_by_size)}")
        logging.info(f"Групп с одинаковым размером файлов: {len(duplicate_size_groups)}")
        logging.info(f"Подозрительных файлов: {suspicious_files_total}")

        all_records: list[DuplicateRecord] = []
        pair_comparisons_total = 0
        pair_comparisons_done = 0

        if not duplicate_size_groups:
            self.report_writer.write(
                records=[],
                suspicious_files_total=0,
                pair_comparisons_total=0,
                pair_comparisons_done=0,
            )
            return

        groups_total = len(duplicate_size_groups)

        for group_index, (size, paths) in enumerate(duplicate_size_groups.items(), start=1):
            paths = sorted(paths)

            logging.info(
                f"Обрабатываю группу {group_index} из {groups_total}. "
                f"Размер: {size} байт. Файлов: {len(paths)}"
            )

            metas = self.loader.load_group(
                paths=paths,
                group_index=group_index,
                groups_total=groups_total,
            )

            if len(metas) < 2:
                continue

            representatives, pair_results = PairPlanner.split_exact_and_fuzzy_candidates(metas)

            fuzzy_pairs = PairPlanner.build_pairs(representatives)
            pair_comparisons_total += len(fuzzy_pairs)

            logging.info(
                f"Группа {group_index}: "
                f"файлов после SHA-256 дедупликации: {len(representatives)}; "
                f"пар для RapidFuzz до фильтра: {len(fuzzy_pairs)}"
            )

            fuzzy_pairs = self.gpu_filter.filter_pairs(fuzzy_pairs)

            rapidfuzz_results = self.comparator.compare_pairs(fuzzy_pairs)
            pair_comparisons_done += len(rapidfuzz_results)

            pair_results.update(rapidfuzz_results)

            group_records = self.resolver.resolve(
                metas=metas,
                pair_results=pair_results,
            )

            all_records.extend(group_records)

            logging.info(
                f"Группа {group_index} завершена. "
                f"Найдено дубликатов в группе: {len(group_records)}"
            )

        self.deleter.delete_records(all_records)

        self.report_writer.write(
            records=all_records,
            suspicious_files_total=suspicious_files_total,
            pair_comparisons_total=pair_comparisons_total,
            pair_comparisons_done=pair_comparisons_done,
        )

        logging.info("Работа скрипта завершена.")

    def _validate_paths(self) -> None:
        logging.info(f"Текущая рабочая директория терминала: {Path.cwd()}")
        logging.info(f"Директория скрипта: {self.config.base_dir}")
        logging.info(f"Проверяемая директория: {self.config.target_dir}")
        logging.info(f"Файл отчёта: {self.config.log_path}")

        if not is_inside_directory(self.config.target_dir, self.config.base_dir):
            raise ValueError(
                f"Запрещено анализировать директорию вне папки скрипта.\n"
                f"Папка скрипта: {self.config.base_dir}\n"
                f"Запрошенная папка: {self.config.target_dir}"
            )

        if not self.config.target_dir.exists():
            raise FileNotFoundError(f"Директория не найдена: {self.config.target_dir}")

        if not self.config.target_dir.is_dir():
            raise NotADirectoryError(f"Это не директория: {self.config.target_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Безопасная очистка почти одинаковых .md файлов одинакового размера. "
            "Финальная проверка выполняется через SHA-256 и RapidFuzz."
        )
    )

    parser.add_argument(
        "--subdir",
        default=".",
        help=(
            "Подпапка внутри директории скрипта. "
            "Путь выше или вне директории скрипта запрещён."
        ),
    )

    parser.add_argument(
        "--delete",
        action="store_true",
        help="Реально удалить найденные дубликаты. Без этого флага будет dry-run.",
    )

    parser.add_argument(
        "--cpu-workers",
        type=int,
        default=8,
        help="Число CPU-процессов для RapidFuzz. Для Ryzen 7 5700X разумное значение: 8.",
    )

    parser.add_argument(
        "--io-workers",
        type=int,
        default=16,
        help="Число потоков для чтения и хеширования файлов. Для Ryzen 7 5700X разумное значение: 16.",
    )

    parser.add_argument(
        "--gpu-prefilter",
        action="store_true",
        help=(
            "Включить CUDA/CPU SimHash prefilter. "
            "Фильтр ускоряет отсечение явно разных пар, но не принимает решение об удалении."
        ),
    )

    parser.add_argument(
        "--simhash-max-distance",
        type=int,
        default=24,
        help=(
            "Максимальная Hamming-дистанция SimHash для допуска пары к RapidFuzz. "
            "Чем меньше значение, тем быстрее, но выше риск пропустить похожие файлы."
        ),
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Более подробное логирование.",
    )

    return parser.parse_args()


def build_config(args: argparse.Namespace) -> CleanerConfig:
    base_dir = script_directory()
    target_dir = (base_dir / args.subdir).resolve()
    log_path = base_dir / LOG_FILENAME

    cpu_workers = max(1, args.cpu_workers)
    io_workers = max(1, args.io_workers)

    return CleanerConfig(
        base_dir=base_dir,
        target_dir=target_dir,
        log_path=log_path,
        delete_enabled=args.delete,
        cpu_workers=cpu_workers,
        io_workers=io_workers,
        gpu_prefilter=args.gpu_prefilter,
        simhash_max_distance=args.simhash_max_distance,
        verbose=args.verbose,
    )


def main() -> None:
    args = parse_args()
    config = build_config(args)

    setup_logging(config.verbose)

    logging.info("Скрипт запущен.")
    logging.info(
        f"Режим: delete={config.delete_enabled}, "
        f"cpu_workers={config.cpu_workers}, "
        f"io_workers={config.io_workers}, "
        f"gpu_prefilter={config.gpu_prefilter}"
    )

    app = DuplicateCleanerApp(config)
    app.run()

    print()
    print("Проверка завершена.")
    print(f"Папка скрипта: {config.base_dir}")
    print(f"Проверенная папка: {config.target_dir}")
    print(f"Лог записан в: {config.log_path}")

    if not config.delete_enabled:
        print("Файлы не удалялись. Для реального удаления запусти скрипт с --delete.")


if __name__ == "__main__":
    try:
        main()

    except Exception as exc:
        print()
        print("КРИТИЧЕСКАЯ ОШИБКА:")
        print(exc)
        print()
        print("Полная трассировка ошибки:")
        traceback.print_exc()
        sys.exit(1)