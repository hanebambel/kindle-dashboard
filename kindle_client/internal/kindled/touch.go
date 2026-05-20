package kindled

import (
	"bufio"
	"encoding/binary"
	"fmt"
	"io"
	"os"
	"regexp"
	"strings"
)

const (
	evSyn = 0
	evKey = 1
	evAbs = 3

	btnTouch       = 330
	absMtPositionX = 53
	absMtPositionY = 54
)

type Tap struct{ X, Y int }

// ReadTaps parses input_event structs from r (16 bytes each) and pushes a Tap
// onto out for each BTN_TOUCH release. Returns when r returns EOF/error.
func ReadTaps(r io.ReadCloser, out chan<- Tap) error {
	defer r.Close()
	br := bufio.NewReader(r)
	buf := make([]byte, 16)
	var x, y int
	for {
		if _, err := io.ReadFull(br, buf); err != nil {
			if err == io.EOF || err == io.ErrUnexpectedEOF {
				return io.EOF
			}
			return err
		}
		etype := binary.LittleEndian.Uint16(buf[8:10])
		code := binary.LittleEndian.Uint16(buf[10:12])
		value := int32(binary.LittleEndian.Uint32(buf[12:16]))
		switch etype {
		case evAbs:
			switch code {
			case absMtPositionX:
				x = int(value)
			case absMtPositionY:
				y = int(value)
			}
		case evKey:
			if code == btnTouch && value == 0 {
				out <- Tap{X: x, Y: y}
			}
		case evSyn:
			// no-op
		}
	}
}

// FindTouchscreen scans /proc/bus/input/devices and returns /dev/input/eventN
// for the first device whose Name contains any of the substrings.
// Defaults to looking for "cyttsp", "synaptics", or "_mt".
func FindTouchscreen(matchers ...string) (string, error) {
	if len(matchers) == 0 {
		matchers = []string{"cyttsp", "synaptics", "_mt"}
	}
	body, err := os.ReadFile("/proc/bus/input/devices")
	if err != nil {
		return "", err
	}
	blocks := strings.Split(string(body), "\n\n")
	re := regexp.MustCompile(`event\d+`)
	for _, blk := range blocks {
		lower := strings.ToLower(blk)
		match := false
		for _, m := range matchers {
			if strings.Contains(lower, strings.ToLower(m)) {
				match = true
				break
			}
		}
		if !match {
			continue
		}
		if dev := re.FindString(blk); dev != "" {
			return "/dev/input/" + dev, nil
		}
	}
	return "", fmt.Errorf("no touchscreen found")
}
