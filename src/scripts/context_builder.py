#!/usr/bin/env python3
"""
Context Builder - Minimalistic Project Context Collector
Version: 1.0
Принцип: Минимализм, Локальный Контекст (4.2, 4.3)

Сборщик контекста проекта для ИИ-партнера.
Формат: минималистичный, структурированный, позиционируемый.
"""

import ast
import fnmatch
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Set, Dict, Callable, Optional, Tuple
import tempfile


# ==================== DATA STRUCTURES ====================

@dataclass
class ExclusionSet:
    """Набор фильтров исключения"""
    dirs: Set[str] = field(default_factory=lambda: {
        "__pycache__", ".git", ".svn", ".hg", ".idea", ".vscode",
        "node_modules", "venv", ".venv", "env", ".env",
        "dist", "build", "out", "target", "bin", "obj",
        ".pytest_cache", ".mypy_cache", ".ruff_cache", "coverage",
        "*.egg-info", "__pycache__", ".cache"
    })
    files: Set[str] = field(default_factory=lambda: {
        ".DS_Store", "Thumbs.db", "desktop.ini",
        "*.pyc", "*.pyo", "*.pyd", "*.so", "*.dll", "*.dylib",
        "*.class", "*.jar", "*.war", "*.ear",
        "*.log", "*.sqlite", "*.db", "*.sqlite3",
        "*.min.js", "*.min.css", "*.map",
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
        "poetry.lock", "Pipfile.lock", "pip-delete-this-directory.txt"
    })
    file_patterns: Set[str] = field(default_factory=lambda: {
        "*.pyc", "*.log", "*.tmp", "*.temp", "*.swp", "*.swo",
        "*.bak", "*.backup", "*~", "#*#", ".#*"
    })
    extensions: Set[str] = field(default_factory=lambda: {
        ".pyc", ".pyo", ".pyd", ".so", ".dll", ".dylib",
        ".class", ".jar", ".war", ".ear", ".log",
        ".min.js", ".min.css", ".map"
    })


class FilePriority(Enum):
    """Приоритеты типов файлов"""
    CRITICAL = 100  # pyproject.toml, README.md, принципиальные документы
    HIGH = 80  # *.py в src/, основные конфиги
    MEDIUM = 50  # Тесты, утилиты, документация в корне
    LOW = 30  # Документация в подпапках, примеры
    NOISE = 0  # Всё остальное, временные файлы


@dataclass
class FileAnalysis:
    """Результат анализа Python файла"""
    imports: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    line_count: int = 0
    code_line_count: int = 0


@dataclass
class FileInfo:
    """Информация о файле для контекста"""
    path: Path
    content: str
    relative_path: str
    priority: FilePriority = FilePriority.MEDIUM
    stats: Dict[str, any] = field(default_factory=dict)
    analysis: Optional[FileAnalysis] = None


# ==================== UTILITY FUNCTIONS ====================

def truncate_content(
        content: str,
        max_lines: int = 100,
        max_chars: int = 5000
) -> str:
    """
    Обрезает содержимое файла, сохраняя начало и конец.

    Если файл слишком большой:
    - Показываем первые max_lines/2 строк
    - Показываем последние max_lines/2 строк
    - Между ними вставляем маркер обрезки
    """
    lines = content.split('\n')
    total_lines = len(lines)

    if total_lines <= max_lines and len(content) <= max_chars:
        return content

    # Слишком много строк
    if total_lines > max_lines:
        half = max_lines // 2
        first_part = lines[:half]
        last_part = lines[-half:] if total_lines > half * 2 else []

        truncated = first_part + [f"\n[... файл обрезан, показано {half * 2} из {total_lines} строк ...]\n"] + last_part
        result = '\n'.join(truncated)
    else:
        result = content

    # Слишком много символов
    if len(result) > max_chars:
        result = result[:max_chars] + f"\n[... файл обрезан, {len(content) - max_chars} символов скрыто ...]"

    return result


def detect_file_priority(file_path: Path) -> FilePriority:
    """Определяет приоритет файла на основе его пути и расширения"""
    path_str = str(file_path)
    name = file_path.name
    parent = file_path.parent.name

    # Критические файлы
    if name in {"pyproject.toml", "README.md", "README.rst", "LICENSE", "MANIFEST.in"}:
        return FilePriority.CRITICAL

    # Основные конфигурационные файлы
    if name in {"setup.py", "setup.cfg", "requirements.txt", "Pipfile", "docker-compose.yml",
                ".env.example", ".gitignore", ".dockerignore", ".pre-commit-config.yaml"}:
        return FilePriority.HIGH

    # Python файлы в важных директориях
    if file_path.suffix == '.py':
        # Ядро системы
        if any(part in path_str for part in ['/src/', '/lib/', '/core/', '/main/', '/app/']):
            if 'test' not in name and 'test' not in path_str:
                return FilePriority.HIGH

        # Тесты
        if 'test' in name or 'tests/' in path_str or '/test_' in path_str:
            return FilePriority.MEDIUM

        # Утилиты
        if any(part in path_str for part in ['/utils/', '/helpers/', '/tools/', '/scripts/']):
            return FilePriority.MEDIUM

    # Документация
    if file_path.suffix in {'.md', '.rst', '.txt'}:
        if parent in {'docs', 'documentation'}:
            return FilePriority.LOW
        return FilePriority.MEDIUM

    # Конфигурационные файлы
    if file_path.suffix in {'.yml', '.yaml', '.json', '.toml', '.cfg', '.ini'}:
        return FilePriority.MEDIUM

    # Остальное
    return FilePriority.NOISE


def match_pattern(filename: str, pattern: str) -> bool:
    """Проверяет соответствие файла паттерну"""
    # Простые имена
    if pattern == filename:
        return True

    # Паттерны с *
    if '*' in pattern:
        return fnmatch.fnmatch(filename, pattern)

    # Расширения
    if pattern.startswith('.'):
        return filename.endswith(pattern)

    return False


# ==================== CORE CLASSES ====================

class PythonFileAnalyzer:
    """Анализатор Python файлов"""

    def analyze(self, content: str) -> FileAnalysis:
        """
        Анализирует Python код, извлекая:
        - Импорты (from X import Y, import Z)
        - Классы (с базовыми классами)
        - Функции (синхронные и асинхронные)
        - Примерное количество строк кода
        """
        analysis = FileAnalysis()
        analysis.line_count = len(content.split('\n'))

        try:
            tree = ast.parse(content)

            for node in ast.walk(tree):
                # Импорты
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        analysis.imports.append(f"import {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    names = ", ".join([alias.name for alias in node.names])
                    analysis.imports.append(f"from {module} import {names}")

                # Классы
                elif isinstance(node, ast.ClassDef):
                    bases = []
                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            bases.append(base.id)
                        elif isinstance(base, ast.Attribute):
                            bases.append(ast.unparse(base))

                    base_str = f"({', '.join(bases)})" if bases else ""
                    analysis.classes.append(f"{node.name}{base_str}")

                # Функции
                elif isinstance(node, ast.FunctionDef):
                    args = self._extract_function_args(node)
                    async_prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
                    analysis.functions.append(f"{async_prefix}{node.name}({args})")

                # Асинхронные функции
                elif isinstance(node, ast.AsyncFunctionDef):
                    args = self._extract_function_args(node)
                    analysis.functions.append(f"async {node.name}({args})")

            # Подсчет строк кода (исключая пустые и комментарии)
            code_lines = [
                line for line in content.split('\n')
                if line.strip() and not line.strip().startswith('#')
            ]
            analysis.code_line_count = len(code_lines)

        except (SyntaxError, RecursionError):
            # Если не можем распарсить, возвращаем пустой анализ
            pass

        return analysis

    def _extract_function_args(self, node: ast.FunctionDef) -> str:
        """Извлекает аргументы функции"""
        args = []

        # Позиционные аргументы
        for arg in node.args.args:
            args.append(arg.arg)

        # *args
        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")

        # **kwargs
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")

        return ", ".join(args)


class ContextBuilder:
    """Основной строитель контекста"""

    def __init__(self, root_path: str):
        self.root = Path(root_path).resolve()
        self.exclusions = ExclusionSet()
        self.custom_filters: List[Dict[str, Callable]] = []
        self.analyzer = PythonFileAnalyzer()
        self._init_default_exclusions()

    def _init_default_exclusions(self):
        """Инициализирует умолчательные фильтры"""
        # Уже установлены в dataclass по умолчанию
        pass

    def get_default_excludes(self) -> ExclusionSet:
        """Возвращает умолчательные исключения"""
        return self.exclusions

    def add_filter(self, name: str, condition: Callable[[Path], bool]):
        """Добавляет кастомный фильтр"""
        self.custom_filters.append({"name": name, "condition": condition})

    def _should_exclude(self, path: Path) -> bool:
        """Определяет, нужно ли исключить путь"""
        # Проверяем стандартные исключения
        if path.is_dir():
            if any(match_pattern(path.name, pattern) for pattern in self.exclusions.dirs):
                return True
        else:
            # Исключаем по точному имени
            if any(match_pattern(path.name, pattern) for pattern in self.exclusions.files):
                return True

            # Исключаем по паттерну
            if any(fnmatch.fnmatch(path.name, pattern) for pattern in self.exclusions.file_patterns):
                return True

            # Исключаем по расширению
            if any(path.suffix == ext for ext in self.exclusions.extensions):
                return True

        # Применяем кастомные фильтры
        for filter_info in self.custom_filters:
            if filter_info["condition"](path):
                return True

        return False

    def apply_filters(self, files: List[Path]) -> List[Path]:
        """Применяет все фильтры к списку файлов"""
        return [f for f in files if not self._should_exclude(f)]

    def _collect_all_files(self) -> List[Path]:
        """Собирает все файлы в проекте рекурсивно"""
        all_files = []

        for root_dir, dirs, files in os.walk(self.root, topdown=True):
            root_path = Path(root_dir)

            # Фильтруем директории
            dirs[:] = [d for d in dirs if not self._should_exclude(root_path / d)]

            # Добавляем файлы
            for file in files:
                file_path = root_path / file
                if not self._should_exclude(file_path):
                    all_files.append(file_path)

        return all_files

    def build_directory_tree(self) -> str:
        """
        Строит минималистичное дерево папок

        Формат:
        project/
        ├── src/
        │   └── core/
        │       └── node.py
        └── tests/
            └── test_node.py
        """
        # Собираем структуру
        structure = defaultdict(list)

        for file_path in self._collect_all_files():
            relative = file_path.relative_to(self.root)
            parts = relative.parts

            if len(parts) == 1:
                structure['.'].append(parts[0])
            else:
                # Добавляем все промежуточные директории
                for i in range(1, len(parts)):
                    dir_path = '/'.join(parts[:i])
                    if i == len(parts) - 1:
                        # Файл
                        structure[dir_path].append(parts[i])
                    else:
                        # Поддиректория (добавим, если еще нет)
                        dir_name = parts[i]
                        if dir_name not in structure[dir_path]:
                            structure[dir_path].append(dir_name)

        # Строим дерево
        lines = []

        def build_tree(node: str, prefix: str = "", is_last: bool = True):
            children = sorted(structure.get(node, []))

            for i, child in enumerate(children):
                child_is_last = i == len(children) - 1
                child_prefix = prefix + ("    " if is_last else "│   ")

                # Определяем тип (директория или файл)
                child_path = f"{node}/{child}" if node != '.' else child
                is_dir = child_path in structure or '/' in child

                icon = "📁 " if is_dir else "📄 "
                if node == '.':
                    lines.append(f"{icon}{child}")
                else:
                    lines.append(f"{prefix}{'└── ' if is_last else '├── '}{icon}{child}")

                if is_dir:
                    build_tree(child_path, child_prefix, child_is_last)

        # Начинаем с корня
        if '.' in structure:
            for child in sorted(structure['.']):
                child_path = child
                is_dir = child_path in structure or '/' in child_path

                icon = "📁 " if is_dir else "📄 "
                lines.append(f"{icon}{child}")

                if is_dir:
                    build_tree(child_path, "", False)

        return "\n".join(lines)

    def prioritize_files(self, file_paths: List[str]) -> List[str]:
        """Сортирует файлы по приоритету (важные первыми)"""
        files_with_priority = []

        for file_str in file_paths:
            file_path = Path(file_str)
            priority = detect_file_priority(file_path)
            files_with_priority.append((priority.value, file_str))

        # Сортируем по приоритету (убывание), затем по имени
        files_with_priority.sort(key=lambda x: (-x[0], x[1]))

        return [file_str for _, file_str in files_with_priority]

    def _read_file(self, file_path: Path) -> Optional[str]:
        """Читает содержимое файла с обработкой ошибок"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except (IOError, OSError, UnicodeDecodeError):
            return None

    def format_file_entry(self, file_info: FileInfo) -> str:
        """
        Форматирует запись о файле

        Формат:
        src/core/node.py
        ╰─ 3 импорта, 2 класса, 5 функций
           class Node:
               def method(self):
                   pass
        """
        lines = []

        # Заголовок с путем
        lines.append(f"📄 {file_info.relative_path}")

        # Статистика
        stats_parts = []
        if file_info.analysis:
            if file_info.analysis.imports:
                count = len(file_info.analysis.imports)
                stats_parts.append(f"{count} импорт{'ов' if count % 10 > 1 else ''}")
            if file_info.analysis.classes:
                count = len(file_info.analysis.classes)
                stats_parts.append(f"{count} класс{'ов' if count % 10 > 1 else ''}")
            if file_info.analysis.functions:
                count = len(file_info.analysis.functions)
                stats_parts.append(f"{count} функци{'й' if count % 10 > 1 else 'я'}")
            if file_info.analysis.line_count:
                stats_parts.append(f"{file_info.analysis.line_count} строк")

        if stats_parts:
            lines.append(f"╰─ {', '.join(stats_parts)}")

        # Содержимое
        if file_info.content.strip():
            # Добавляем отступ для содержимого
            content_lines = file_info.content.split('\n')
            for i, line in enumerate(content_lines):
                if i == 0:
                    lines.append(f"   {line}")
                else:
                    lines.append(f"   {line}")

        return '\n'.join(lines)

    def build(self) -> str:
        """
        Собирает полный контекст

        Структура вывода:
        ========== КОНТЕКСТ ПРОЕКТА ==========

        [ДЕРЕВО ПРОЕКТА]

        ========== СОДЕРЖАНИЕ ==========

        [ФАЙЛ 1]
        [содержимое]

        [ФАЙЛ 2]
        [содержимое]

        ========== ДЛЯ ИИ ==========
        [инструкции]
        """
        parts = []

        # 1. Заголовок
        parts.append("=" * 40)
        parts.append(f"КОНТЕКСТ ПРОЕКТА: {self.root.name}")
        parts.append(f"Собрано: {self.__class__.__name__}")
        parts.append("=" * 40)

        # 2. Дерево структуры
        parts.append("\n🌳 СТРУКТУРА ПРОЕКТА:\n")
        try:
            tree = self.build_directory_tree()
            parts.append(tree)
        except Exception as e:
            parts.append(f"⚠️ Не удалось построить дерево: {e}")

        # 3. Содержимое файлов
        parts.append("\n" + "=" * 40)
        parts.append("📁 СОДЕРЖАНИЕ ФАЙЛОВ:")
        parts.append("=" * 40 + "\n")

        # Собираем и сортируем файлы
        all_files = self._collect_all_files()
        if not all_files:
            parts.append("❌ Файлы не найдены")
        else:
            # Сортируем по приоритету
            file_strings = [str(f.relative_to(self.root)) for f in all_files]
            prioritized = self.prioritize_files(file_strings)

            # Ограничиваем количество файлов для контекста
            max_files = 50
            if len(prioritized) > max_files:
                parts.append(f"📊 Показано {max_files} из {len(prioritized)} файлов (остальные скрыты)\n")
                prioritized = prioritized[:max_files]

            # Читаем и форматируем каждый файл
            for i, file_str in enumerate(prioritized, 1):
                file_path = self.root / file_str
                content = self._read_file(file_path)

                if content:
                    # Анализируем Python файлы
                    analysis = None
                    if file_path.suffix == '.py':
                        analysis = self.analyzer.analyze(content)

                    # Обрезаем большие файлы
                    truncated = truncate_content(content, max_lines=100, max_chars=5000)

                    file_info = FileInfo(
                        path=file_path,
                        content=truncated,
                        relative_path=file_str,
                        priority=detect_file_priority(file_path),
                        analysis=analysis
                    )

                    formatted = self.format_file_entry(file_info)
                    parts.append(formatted)

                    # Разделитель между файлами (кроме последнего)
                    if i < len(prioritized):
                        parts.append("\n" + "-" * 40 + "\n")

        # 4. Инструкции для ИИ
        parts.append("\n" + "=" * 40)
        parts.append("🤖 КОНТЕКСТ ДЛЯ ИИ:")
        parts.append("=" * 40)
        parts.append("""
Ты видишь структуру и содержимое проекта. Используй эту информацию для:
1. Понимания архитектуры и зависимостей
2. Анализа существующего кода
3. Генерации кода, который интегрируется с проектом

Обрати внимание на:
• Структуру проекта (дерево вверху)
• Приоритетные файлы (идут первыми)
• Анализ Python файлов (импорты, классы, функции)

При генерации кода:
1. Следуй существующим паттернам
2. Используй уже импортированные модули
3. Поддерживай стиль кода проекта
4. Учитывай ограничения проекта

Файлы отсортированы по важности. Начни с первых.
""")

        return "\n".join(parts)


# ==================== MAIN & CLI ====================

def main():
    """Точка входа CLI"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Сборщик контекста проекта для ИИ (минималистичный)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  %(prog)s                         # Собрать контекст текущей директории
  %(prog)s -p /path/to/project     # Собрать контекст указанного проекта
  %(prog)s -o context.txt          # Сохранить в файл
  %(prog)s -v                      # Подробный вывод
        """
    )

    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Путь к проекту (по умолчанию: текущая директория)"
    )

    parser.add_argument(
        "-o", "--output",
        help="Сохранить контекст в файл"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Подробный вывод"
    )

    parser.add_argument(
        "--add-exclude",
        action="append",
        default=[],
        help="Добавить кастомное исключение (паттерн)"
    )

    parser.add_argument(
        "--no-truncate",
        action="store_true",
        help="Не обрезать большие файлы"
    )

    args = parser.parse_args()

    try:
        # Инициализируем сборщик
        builder = ContextBuilder(args.path)

        # Добавляем кастомные исключения
        for pattern in args.add_exclude:
            builder.add_filter(f"custom_{pattern}", lambda p, pat=pattern: fnmatch.fnmatch(p.name, pat))

        if args.verbose:
            print(f"🔍 Сканирую проект: {builder.root}")
            excludes = builder.get_default_excludes()
            print(f"📋 Исключения: {len(excludes.dirs)} директорий, {len(excludes.files)} файлов")

        # Собираем контекст
        context = builder.build()

        # Выводим или сохраняем
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(context)
            print(f"✅ Контекст сохранен в: {args.output}")
            print(f"📏 Размер: {len(context):,} символов")
        else:
            print(context)

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())