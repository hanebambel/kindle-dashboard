.PHONY: build clean test

GOTOOLCHAIN ?= go1.19.13
GOOS    ?= linux
GOARCH  ?= arm
GOARM   ?= 7
BIN     := build/kindled

build: clean $(BIN)

$(BIN):
	mkdir -p build
	GOTOOLCHAIN=$(GOTOOLCHAIN) GOOS=$(GOOS) GOARCH=$(GOARCH) GOARM=$(GOARM) CGO_ENABLED=0 \
		go build -ldflags="-s -w" -o $(BIN) ./cmd/kindled

test:
	GOTOOLCHAIN=$(GOTOOLCHAIN) go test ./...

clean:
	rm -rf build
