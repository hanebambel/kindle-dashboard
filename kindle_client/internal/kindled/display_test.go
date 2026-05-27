package kindled

import (
	"bytes"
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"
	"testing"
)

func TestDisplayWritesPNGAndRunsEips(t *testing.T) {
	dir := t.TempDir()
	pngPath := filepath.Join(dir, "dash.png")
	eipsArgs := [][]string{}
	src := rgbaPNG(t)

	d := &Display{
		PNGPath: pngPath,
		EipsRun: func(args ...string) (string, error) {
			eipsArgs = append(eipsArgs, args)
			return "", nil
		},
	}
	if err := d.Show(src); err != nil {
		t.Fatal(err)
	}
	got, err := os.ReadFile(pngPath)
	if err != nil {
		t.Fatal(err)
	}
	img, err := png.Decode(bytes.NewReader(got))
	if err != nil {
		t.Fatal(err)
	}
	grayImg, ok := img.(*image.Gray)
	if !ok {
		t.Fatalf("decoded type=%T, want *image.Gray", img)
	}
	if grayImg.GrayAt(0, 0).Y == grayImg.GrayAt(1, 0).Y {
		t.Fatalf("expected grayscale conversion to preserve different pixel values")
	}
	if len(eipsArgs) != 1 {
		t.Fatalf("eips calls=%d", len(eipsArgs))
	}
	want := []string{"-f", "-g", pngPath}
	for i := range want {
		if eipsArgs[0][i] != want[i] {
			t.Errorf("eips args=%v", eipsArgs[0])
			break
		}
	}
}

func TestTo8BitGrayscalePNGConvertsRGBA(t *testing.T) {
	converted, err := to8BitGrayscalePNG(rgbaPNG(t))
	if err != nil {
		t.Fatal(err)
	}
	img, err := png.Decode(bytes.NewReader(converted))
	if err != nil {
		t.Fatal(err)
	}
	if _, ok := img.(*image.Gray); !ok {
		t.Fatalf("decoded type=%T, want *image.Gray", img)
	}
}

func rgbaPNG(t *testing.T) []byte {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, 2, 1))
	img.Set(0, 0, color.RGBA{R: 255, G: 0, B: 0, A: 255})
	img.Set(1, 0, color.RGBA{R: 255, G: 255, B: 255, A: 255})
	buf := &bytes.Buffer{}
	if err := png.Encode(buf, img); err != nil {
		t.Fatal(err)
	}
	return buf.Bytes()
}

func TestDisplayIncludesEipsOutputOnFailure(t *testing.T) {
	d := &Display{
		PNGPath: filepath.Join(t.TempDir(), "dash.png"),
		EipsRun: func(args ...string) (string, error) {
			return "bad image header", os.ErrInvalid
		},
	}

	err := d.Show(rgbaPNG(t))
	if err == nil {
		t.Fatal("expected error")
	}
	if got := err.Error(); got != "invalid argument: bad image header" {
		t.Fatalf("error=%q", got)
	}
}
