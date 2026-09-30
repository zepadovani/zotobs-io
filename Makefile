.PHONY: test install
test:
	uv run --with pymupdf --with pytest pytest -q
install:
	./install.sh --all
