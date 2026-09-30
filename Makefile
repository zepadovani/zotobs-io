.PHONY: test install xpi
test:
	uv run --with pymupdf --with pytest python -m pytest -q
install:
	./install.sh --all
xpi:
	./extension/build.sh
