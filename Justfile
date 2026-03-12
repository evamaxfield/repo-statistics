# list all available commands
default:
  just --list

###############################################################################
# Basic project and env management

# clean all build, python, and lint files
clean:
	rm -fr dist
	rm -fr .eggs
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +
	rm -fr .mypy_cache
	rm -fr .pytest_cache
	rm -fr .ruff_cache
	rm -fr build

# install with all deps
install:
	pip install uv
	uv pip install -e ".[lint,dev,coiled]"

# run linting
lint:
	ruff check . --fix
	ruff format . --fix
	ty check

# test all files
test:
	pytest

###############################################################################
# Release and versioning

# tag a new version
tag-for-release version:
	git tag -a "{{version}}" -m "{{version}}"
	echo "Tagged: $(git tag --sort=-version:refname| head -n 1)"

# release a new version
release:
	git push --follow-tags

###############################################################################
# Cookiecutter management

# update this repo using latest cookiecutter
update-from-cookiecutter:
	pip install cookiecutter
	cookiecutter gh:evamaxfield/pyproject-template --config-file .cookiecutter.yaml --no-input --overwrite-if-exists --output-dir ..

