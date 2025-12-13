.PHONY: test install clean context help

help:
	@echo "Команды для сборщика контекста:"
	@echo "  make install    - Установить зависимости"
	@echo "  make test       - Запустить тесты"
	@echo "  make context    - Собрать контекст текущего проекта"
	@echo "  make clean      - Очистить временные файлы"

install:
	pip install -e .

test:
	pytest test_context_builder_impl.py -v
	pytest test_context_builder_spec.py -v

context:
	python context_builder.py -o project_context.txt

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type f -name "project_context.txt" -delete
	find . -type f -name "*.log" -delete

run-example:
	@echo "Создаем пример проекта..."
	@mkdir -p example/src/core example/tests
	@echo "class Node:\n    pass" > example/src/core/node.py
	@echo "def test_node():\n    pass" > example/tests/test_node.py
	@echo "# Пример проекта" > example/README.md
	@echo "[project]\nname = 'example'" > example/pyproject.toml
	@python context_builder.py example/ -o example_context.txt
	@echo "Контекст сохранен в example_context.txt"