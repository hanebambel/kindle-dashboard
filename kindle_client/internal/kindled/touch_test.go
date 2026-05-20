package kindled

import (
	"bytes"
	"encoding/binary"
	"io"
	"testing"
)

func packEvent(t uint16, c uint16, v int32) []byte {
	buf := make([]byte, 16)
	// sec, usec, type, code, value (little-endian on ARM)
	binary.LittleEndian.PutUint32(buf[0:4], 0)
	binary.LittleEndian.PutUint32(buf[4:8], 0)
	binary.LittleEndian.PutUint16(buf[8:10], t)
	binary.LittleEndian.PutUint16(buf[10:12], c)
	binary.LittleEndian.PutUint32(buf[12:16], uint32(v))
	return buf
}

func TestReadTapsEmitsOnButtonRelease(t *testing.T) {
	var buf bytes.Buffer
	buf.Write(packEvent(3, 53, 432))  // EV_ABS ABS_MT_POSITION_X=432
	buf.Write(packEvent(3, 54, 600))  // EV_ABS ABS_MT_POSITION_Y=600
	buf.Write(packEvent(1, 330, 1))   // EV_KEY BTN_TOUCH down
	buf.Write(packEvent(0, 0, 0))     // EV_SYN
	buf.Write(packEvent(1, 330, 0))   // EV_KEY BTN_TOUCH up   <-- emit here

	taps := make(chan Tap, 4)
	err := ReadTaps(io.NopCloser(&buf), taps)
	if err != nil && err != io.EOF {
		t.Fatalf("ReadTaps: %v", err)
	}
	close(taps)

	var got []Tap
	for tap := range taps {
		got = append(got, tap)
	}
	if len(got) != 1 || got[0].X != 432 || got[0].Y != 600 {
		t.Errorf("taps=%+v", got)
	}
}

func TestReadTapsIgnoresMoveWithoutRelease(t *testing.T) {
	// Move/sync events without a BTN_TOUCH release should not emit.
	var buf bytes.Buffer
	buf.Write(packEvent(3, 53, 100))
	buf.Write(packEvent(3, 54, 200))
	buf.Write(packEvent(0, 0, 0))

	taps := make(chan Tap, 4)
	err := ReadTaps(io.NopCloser(&buf), taps)
	if err != nil && err != io.EOF {
		t.Fatalf("ReadTaps: %v", err)
	}
	close(taps)
	if got := len(taps); got != 0 {
		t.Errorf("expected 0 taps, got %d", got)
	}
}
