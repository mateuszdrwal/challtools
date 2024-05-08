
dependencies:
	pip install -r requirements.txt

dependencies-dev:
	pip install -r requirements-dev.txt

mypy:
	python -m mypy --strict --exclude build .

test:
	python -m pytest .

.PHONY: dependencies dependencies-dev mypy test
