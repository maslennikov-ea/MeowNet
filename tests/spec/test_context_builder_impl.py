"""
Конкретные тесты для проверки нашей реализации.
Наследуется от абстрактных тестов и предоставляет реальные реализации.
"""

import pytest
# Импортируем нашу реализацию
from src.scripts.context_builder import ContextBuilder, PythonFileAnalyzer

# Импортируем абстрактные тесты
from tests.spec.context_builder_spec import ContextBuilderCompliance


class TestOurImplementation(ContextBuilderCompliance):
    """
    Конкретные тесты нашей реализации.
    Наследует все абстрактные тесты и предоставляет реальные фикстуры.
    """

    @pytest.fixture
    def implementation(self):
        """Возвращает экземпляр нашей реализации"""
        return ContextBuilder("/dummy/path")

    @pytest.fixture
    def analyzer_implementation(self):
        """Возвращает экземпляр нашего анализатора"""
        return PythonFileAnalyzer()

    # Можно добавить дополнительные тесты, специфичные для реализации
    def test_our_specific_feature(self):
        """Дополнительный тест нашей реализации"""
        builder = ContextBuilder("/dummy/path")
        assert builder is not None


# Запуск тестов
if __name__ == "__main__":
    # Генерация отчета о соответствии
    from context_builder_spec import ImplementationValidator

    print(ImplementationValidator.generate_compliance_report(None))

    # Запуск тестов
    pytest.main([__file__, "-v"])
