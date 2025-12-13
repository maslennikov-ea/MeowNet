#!/usr/bin/env python3
"""
Context Builder - Единая спецификация и тесты
=============================================

Этот файл является:
1. СПЕЦИФИКАЦИЕЙ требований к сборщику контекста
2. ТЕСТАМИ проверки реализации
3. ДОКУМЕНТАЦИЕЙ архитектуры

Принцип: "Specification as a Single Source of Truth"
"""

import pytest
import tempfile
import ast
import fnmatch
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Set, Dict, Callable, Optional, Tuple

# ============================================================================
# ЧАСТЬ 1: СПЕЦИФИКАЦИЯ ТРЕБОВАНИЙ (как код)
# ============================================================================

class ContextBuilderSpecification:
    """
    Спецификация требований к сборщику контекста.
    Этот класс определяет ЧТО должно делать, а не КАК.
    """
    
    # ---------- Требование 1: Фильтры исключения ----------
    @dataclass
    class ExclusionSetSpec:
        """Спецификация набора фильтров исключения"""
        dirs: Set[str] = field(default_factory=lambda: {
            "__pycache__", ".git", ".svn", ".hg", ".idea", ".vscode",
            "node_modules", "venv", ".venv", "env", ".env",
            "dist", "build", "out", "target", "bin", "obj",
            ".pytest_cache", ".mypy_cache", ".ruff_cache", "coverage",
            "*.egg-info", ".cache"
        })
        files: Set[str] = field(default_factory=lambda: {
            ".DS_Store", "Thumbs.db", "desktop.ini",
            "*.pyc", "*.pyo", "*.pyd", "*.so", "*.dll", "*.dylib",
            "*.log", "*.sqlite", "*.db", "*.sqlite3",
            "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
            "poetry.lock", "Pipfile.lock"
        })
        file_patterns: Set[str] = field(default_factory=lambda: {
            "*.pyc", "*.log", "*.tmp", "*.temp", "*.swp", "*.swo",
            "*.bak", "*.backup", "*~", "#*#", ".#*"
        })
        extensions: Set[str] = field(default_factory=lambda: {
            ".pyc", ".pyo", ".pyd", ".so", ".dll", ".dylib",
            ".log", ".min.js", ".min.css", ".map"
        })
    
    # ---------- Требование 2: Приоритеты файлов ----------
    class FilePrioritySpec(Enum):
        """Спецификация приоритетов файлов"""
        CRITICAL = 100    # pyproject.toml, README.md
        HIGH = 80         # *.py в src/, основные конфиги
        MEDIUM = 50       # Тесты, утилиты
        LOW = 30          # Документация в подпапках
        NOISE = 0         # Всё остальное
    
    # ---------- Требование 3: Анализ Python файлов ----------
    @dataclass
    class FileAnalysisSpec:
        """Спецификация анализа Python файла"""
        imports: List[str]
        classes: List[str]
        functions: List[str]
        line_count: int
        code_line_count: int
        
        @classmethod
        def from_code(cls, code: str) -> 'FileAnalysisSpec':
            """Создает спецификацию анализа из кода"""
            imports = []
            classes = []
            functions = []
            line_count = len(code.split('\n'))
            code_line_count = 0
            
            try:
                tree = ast.parse(code)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.append(f"import {alias.name}")
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        names = ", ".join([alias.name for alias in node.names])
                        imports.append(f"from {module} import {names}")
                    elif isinstance(node, ast.ClassDef):
                        bases = []
                        for base in node.bases:
                            if isinstance(base, ast.Name):
                                bases.append(base.id)
                        base_str = f"({', '.join(bases)})" if bases else ""
                        classes.append(f"{node.name}{base_str}")
                    elif isinstance(node, ast.FunctionDef):
                        args = [arg.arg for arg in node.args.args]
                        async_prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
                        functions.append(f"{async_prefix}{node.name}({', '.join(args)})")
                
                # Подсчет строк кода
                code_lines = [
                    line for line in code.split('\n')
                    if line.strip() and not line.strip().startswith('#')
                ]
                code_line_count = len(code_lines)
                
            except (SyntaxError, RecursionError):
                pass
            
            return cls(
                imports=imports,
                classes=classes,
                functions=functions,
                line_count=line_count,
                code_line_count=code_line_count
            )
    
    # ---------- Требование 4: Формат вывода ----------
    @staticmethod
    def expected_output_format() -> Dict[str, str]:
        """Спецификация формата вывода"""
        return {
            "project_structure": "Должно начинаться с '🌳 СТРУКТУРА ПРОЕКТА:'",
            "file_content": "Должен содержать секцию '📁 СОДЕРЖАНИЕ ФАЙЛОВ:'",
            "ai_context": "Должен содержать секцию '🤖 КОНТЕКСТ ДЛЯ ИИ:'",
            "file_entry": "Каждый файл должен начинаться с '📄 ' и содержать путь",
            "tree_indent": "Дерево должно использовать отступы '│   ', '├── ', '└── '",
            "truncation_marker": "Обрезанные файлы должны содержать '[... файл обрезан'",
        }
    
    # ---------- Требование 5: Поведение ----------
    @staticmethod
    def behavioral_requirements() -> List[str]:
        """Спецификация поведенческих требований"""
        return [
            "1. Исключать служебные директории (__pycache__, .git, etc)",
            "2. Показывать структуру проекта в виде дерева",
            "3. Анализировать Python файлы (импорты, классы, функции)",
            "4. Сортировать файлы по приоритету (важные первыми)",
            "5. Обрезать большие файлы, сохраняя начало и конец",
            "6. Поддерживать кастомные фильтры исключения",
            "7. Сохранять относительные пути в выводе",
            "8. Форматировать вывод для удобства чтения ИИ",
        ]


# ============================================================================
# ЧАСТЬ 2: ИНТЕРФЕЙСЫ РЕАЛИЗАЦИИ (что должно быть реализовано)
# ============================================================================

class IContextBuilder:
    """Интерфейс, который должна реализовывать любая реализация сборщика"""
    
    def __init__(self, root_path: str):
        """Инициализация с путем к корню проекта"""
        raise NotImplementedError
    
    def get_default_excludes(self) -> ContextBuilderSpecification.ExclusionSetSpec:
        """Возвращает умолчательные фильтры исключения"""
        raise NotImplementedError
    
    def add_filter(self, name: str, condition: Callable[[Path], bool]):
        """Добавляет кастомный фильтр"""
        raise NotImplementedError
    
    def build_directory_tree(self) -> str:
        """Строит минималистичное дерево папок"""
        raise NotImplementedError
    
    def prioritize_files(self, file_paths: List[str]) -> List[str]:
        """Сортирует файлы по приоритету"""
        raise NotImplementedError
    
    def format_file_entry(self, file_info: 'FileInfo') -> str:
        """Форматирует запись о файле"""
        raise NotImplementedError
    
    def build(self) -> str:
        """Собирает полный контекст"""
        raise NotImplementedError


class IPythonFileAnalyzer:
    """Интерфейс анализатора Python файлов"""
    
    def analyze(self, content: str) -> ContextBuilderSpecification.FileAnalysisSpec:
        """Анализирует Python код"""
        raise NotImplementedError


# ============================================================================
# ЧАСТЬ 3: ТЕСТЫ, ПРОВЕРЯЮЩИЕ СООТВЕТСТВИЕ СПЕЦИФИКАЦИИ
# ============================================================================

class ContextBuilderCompliance:
    """
    Тесты, проверяющие, что РЕАЛИЗАЦИЯ соответствует СПЕЦИФИКАЦИИ.
    
    Важно: Эти тесты НЕ тестируют конкретную реализацию, 
    а проверяют соответствие интерфейсу и требованиям.
    """
    
    # ---------- Фикстура для получения реализации ----------
    @pytest.fixture
    def implementation(self):
        """
        Фикстура, которая должна быть переопределена в тестовом файле,
        чтобы возвращать экземпляр реализации IContextBuilder.
        """
        raise NotImplementedError(
            "Переопределите эту фикстуру в тестах, "
            "чтобы вернуть вашу реализацию ContextBuilder"
        )
    
    @pytest.fixture
    def analyzer_implementation(self):
        """
        Фикстура для реализации анализатора Python файлов.
        """
        raise NotImplementedError(
            "Переопределите эту фикстура в тестах, "
            "чтобы вернуть вашу реализацию PythonFileAnalyzer"
        )
    
    # ---------- Тесты соответствия спецификации ----------
    
    def test_1_exclusion_filters_spec(self, implementation):
        """Тест 1: Фильтры исключения должны соответствовать спецификации"""
        spec = ContextBuilderSpecification.ExclusionSetSpec()
        impl = implementation.get_default_excludes()
        
        # Проверяем, что все обязательные исключения присутствуют
        assert "__pycache__" in impl.dirs
        assert ".git" in impl.dirs
        assert "*.pyc" in impl.file_patterns
        assert ".pyc" in impl.extensions
        
        # Проверяем, что важные файлы НЕ исключены
        assert "pyproject.toml" not in impl.files
        assert "README.md" not in impl.files
        assert ".env.example" not in impl.files
    
    def test_2_directory_tree_minimalism(self, implementation):
        """Тест 2: Дерево папок должно быть минималистичным"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Создаем структуру с шумом
            (Path(tmpdir) / "src" / "core" / "__pycache__").mkdir(parents=True)
            (Path(tmpdir) / ".git").mkdir()
            (Path(tmpdir) / "src" / "core" / "node.py").write_text("class Node: pass")
            
            builder = implementation.__class__(tmpdir)
            tree = builder.build_directory_tree()
            
            # Дерево не должно содержать исключенные элементы
            assert "__pycache__" not in tree
            assert ".git" not in tree
            
            # Должно содержать важные элементы
            assert "src/" in tree or "src" in tree
            assert "core/" in tree or "core" in tree
            assert "node.py" in tree
            
            # Должны быть отступы для вложенности
            assert "    " in tree or "│   " in tree or "├── " in tree or "└── " in tree
    
    def test_3_python_file_analysis_spec(self, analyzer_implementation):
        """Тест 3: Анализ Python файлов должен соответствовать спецификации"""
        test_code = '''
"""Module docstring."""
from typing import List, Dict
import os

class ImportantClass:
    """A very important class."""
    
    def method_one(self) -> str:
        return "hello"
    
    def method_two(self, param: int) -> int:
        return param * 2

def helper_function() -> bool:
    return True
'''
        
        # Спецификация того, что должно быть
        spec_analysis = ContextBuilderSpecification.FileAnalysisSpec.from_code(test_code)
        
        # Реализация
        impl_analysis = analyzer_implementation.analyze(test_code)
        
        # Проверяем соответствие
        assert set(spec_analysis.imports) == set(impl_analysis.imports)
        assert set(spec_analysis.classes) == set(impl_analysis.classes)
        assert set(spec_analysis.functions) == set(impl_analysis.functions)
    
    def test_4_file_priority_sorting(self, implementation):
        """Тест 4: Сортировка файлов по приоритету"""
        files = [
            "docs/notes.md",
            "src/__init__.py",
            "src/core/node.py",
            "tests/test_node.py",
            "pyproject.toml",
            ".gitignore",
            "README.md",
            "build/script.js",
        ]
        
        prioritized = implementation.prioritize_files(files)
        
        # Критические файлы должны быть в начале
        critical_files = {"pyproject.toml", "README.md"}
        assert any(f in critical_files for f in prioritized[:2])
        
        # Высокоприоритетные файлы должны быть раньше средних
        src_index = next(i for i, f in enumerate(prioritized) if "src/core" in f)
        test_index = next(i for i, f in enumerate(prioritized) if "tests/test" in f)
        assert src_index < test_index
    
    def test_5_output_format_compliance(self, implementation):
        """Тест 5: Формат вывода должен соответствовать спецификации"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Минимальный проект
            (Path(tmpdir) / "test.py").write_text("print('hello')")
            (Path(tmpdir) / "README.md").write_text("# Test")
            
            builder = implementation.__class__(tmpdir)
            output = builder.build()
            
            format_spec = ContextBuilderSpecification.expected_output_format()
            
            # Проверяем обязательные секции
            assert "СТРУКТУРА ПРОЕКТА" in output or "СТРУКТУРА" in output
            assert "СОДЕРЖАНИЕ ФАЙЛОВ" in output or "СОДЕРЖАНИЕ" in output
            assert "КОНТЕКСТ ДЛЯ ИИ" in output or "ДЛЯ ИИ" in output
            
            # Проверяем формат записи файла
            assert "test.py" in output
            assert "README.md" in output
    
    def test_6_custom_filters_support(self, implementation):
        """Тест 6: Поддержка кастомных фильтров"""
        # Тест требует, чтобы реализация поддерживала add_filter
        # Это проверяется через наличие метода
        assert hasattr(implementation, 'add_filter')
        assert callable(implementation.add_filter)
    
    def test_7_file_truncation(self):
        """Тест 7: Обрезка больших файлов (тест утилиты)"""
        # Создаем большой файл
        lines = [f"# Line {i}" for i in range(500)]
        content = "\n".join(lines)
        
        # Ищем функцию truncate в реализации
        # (это может быть отдельная функция или метод)
        try:
            from context_builder import truncate_content
            truncated = truncate_content(content, max_lines=50, max_chars=1000)
            
            assert len(truncated.split('\n')) <= 60  # 50 + маркеры
            assert "[... файл обрезан" in truncated
            assert "# Line 0" in truncated  # Начало сохранено
            assert "# Line 499" not in truncated  # Конец обрезан
            
        except ImportError:
            # Если функции нет, тест пропускается
            pytest.skip("Функция truncate_content не найдена в реализации")
    
    def test_8_behavioral_compliance(self, implementation):
        """Тест 8: Общее соответствие поведенческим требованиям"""
        requirements = ContextBuilderSpecification.behavioral_requirements()
        
        # Проверяем основные поведенческие аспекты
        with tempfile.TemporaryDirectory() as tmpdir:
            # Создаем тестовую структуру
            (Path(tmpdir) / "src" / "file.py").write_text("def foo(): pass")
            (Path(tmpdir) / "__pycache__" / "cache.pyc").mkdir(parents=True)
            
            builder = implementation.__class__(tmpdir)
            output = builder.build()
            
            # 1. Должен исключать служебные директории
            assert "__pycache__" not in output
            
            # 2. Должен показывать структуру
            assert "src/" in output or "src" in output
            
            # 3. Должен анализировать Python файлы
            if "file.py" in output:
                assert "def foo()" in output or "foo" in output


# ============================================================================
# ЧАСТЬ 4: УТИЛИТЫ ДЛЯ ПРОВЕРКИ РЕАЛИЗАЦИИ
# ============================================================================

class ImplementationValidator:
    """
    Валидатор, который проверяет конкретную реализацию 
    на соответствие спецификации.
    """
    
    @classmethod
    def validate_context_builder(cls, implementation_class) -> Dict[str, bool]:
        """
        Проверяет класс реализации на соответствие интерфейсу IContextBuilder.
        Возвращает словарь с результатами проверки.
        """
        results = {}
        
        # Проверяем обязательные методы
        required_methods = [
            '__init__',
            'get_default_excludes',
            'add_filter', 
            'build_directory_tree',
            'prioritize_files',
            'format_file_entry',
            'build'
        ]
        
        for method in required_methods:
            has_method = hasattr(implementation_class, method)
            is_callable = callable(getattr(implementation_class, method, None))
            results[f"method_{method}"] = has_method and is_callable
        
        # Проверяем, что возвращаемые типы соответствуют спецификации
        try:
            instance = implementation_class("/tmp")
            excludes = instance.get_default_excludes()
            results["excludes_type"] = isinstance(
                excludes, 
                ContextBuilderSpecification.ExclusionSetSpec
            )
        except:
            results["excludes_type"] = False
        
        return results
    
    @classmethod
    def generate_compliance_report(cls, implementation_module) -> str:
        """Генерирует отчет о соответствии реализации спецификации"""
        report = []
        report.append("=" * 60)
        report.append("ОТЧЕТ О СООТВЕТСТВИИ СПЕЦИФИКАЦИИ")
        report.append("=" * 60)
        
        try:
            # Проверяем ContextBuilder
            from context_builder import ContextBuilder
            builder_results = cls.validate_context_builder(ContextBuilder)
            
            report.append("\n[ContextBuilder]")
            for method, passed in builder_results.items():
                status = "✅" if passed else "❌"
                report.append(f"  {status} {method}: {passed}")
            
            # Проверяем PythonFileAnalyzer
            from context_builder import PythonFileAnalyzer
            analyzer = PythonFileAnalyzer()
            has_analyze = hasattr(analyzer, 'analyze') and callable(analyzer.analyze)
            
            report.append("\n[PythonFileAnalyzer]")
            report.append(f"  {'✅' if has_analyze else '❌'} analyze method: {has_analyze}")
            
            # Общая оценка
            all_passed = all(builder_results.values()) and has_analyze
            report.append("\n" + "=" * 60)
            report.append(f"ИТОГ: {'СООТВЕТСТВУЕТ' if all_passed else 'НЕ СООТВЕТСТВУЕТ'}")
            
        except ImportError as e:
            report.append(f"\n❌ Не удалось импортировать реализацию: {e}")
        except Exception as e:
            report.append(f"\n❌ Ошибка при проверке: {e}")
        
        return "\n".join(report)


# ============================================================================
# ЧАСТЬ 5: ЗАПУСК ТЕСТОВ И ГЕНЕРАЦИЯ ОТЧЕТА
# ============================================================================

if __name__ == "__main__":
    """
    Запуск тестов и генерация отчета о соответствии.
    
    Использование:
      python context_builder_spec.py --test    # запустить тесты
      python context_builder_spec.py --report  # сгенерировать отчет
      python context_builder_spec.py --all     # всё вместе
    """
    
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Спецификация и тесты сборщика контекста")
    parser.add_argument("--test", action="store_true", help="Запустить тесты")
    parser.add_argument("--report", action="store_true", help="Сгенерировать отчет")
    parser.add_argument("--all", action="store_true", help="Выполнить всё")
    
    args = parser.parse_args()
    
    if not any([args.test, args.report, args.all]):
        parser.print_help()
        sys.exit(1)
    
    # Генерация отчета
    if args.report or args.all:
        print("\n" + ImplementationValidator.generate_compliance_report(None))
    
    # Запуск тестов
    if args.test or args.all:
        print("\n" + "=" * 60)
        print("ЗАПУСК ТЕСТОВ СООТВЕТСТВИЯ СПЕЦИФИКАЦИИ")
        print("=" * 60)
        
        # Для запуска тестов нужна реальная реализация
        # В этом файле тесты являются абстрактными
        # Реальные тесты будут в отдельном файле
        
        print("\n⚠️  Тесты в этом файле являются абстрактными.")
        print("Для запуска реальных тестов создайте файл test_implementation.py")
        print("с переопределением фикстур implementation и analyzer_implementation")
