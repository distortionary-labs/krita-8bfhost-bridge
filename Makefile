PYTHON ?= python3
PYTEST ?= $(PYTHON) -m pytest
VERSION := $(shell sed -n 's/^__version__ = "\(.*\)"/\1/p' krita_8bfhost_bridge/__init__.py)

.PHONY: test lint format package install krita-smoke clean

test:
	$(PYTEST) -q

lint:
	ruff check krita_8bfhost_bridge tests
	ruff format --check krita_8bfhost_bridge tests

format:
	ruff format krita_8bfhost_bridge tests

# A zip Krita can import with Tools > Scripts > Import Python Plugin from File.
package:
	rm -rf dist && mkdir -p dist
	zip -qr dist/krita-8bfhost-bridge-$(VERSION).zip krita_8bfhost_bridge.desktop krita_8bfhost_bridge LICENSE \
		-x '*/__pycache__/*' '*.pyc'
	@echo dist/krita-8bfhost-bridge-$(VERSION).zip

install:
	scripts/install.sh

# Runs the plug-in inside a real Krita with a throwaway profile under Xvfb.
krita-smoke:
	tests/krita_smoke/run.sh

clean:
	rm -rf dist .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
