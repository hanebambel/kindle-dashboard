.PHONY: build clean test

GOOS    ?= linux
GOARCH  ?= arm
GOARM   ?= 7
BIN     := build/kindled

build: $(BIN)

$(BIN):
	mkdir -p build
	GOOS=$(GOOS) GOARCH=$(GOARCH) GOARM=$(GOARM) CGO_ENABLED=0 \
		go build -ldflags="-s -w" -o $(BIN) ./cmd/kindled

test:
	go test ./...

clean:
	rm -rf build
