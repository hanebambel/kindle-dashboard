package kindled

import (
	"bytes"
	"fmt"
	"image"
	"image/color"
	"image/png"
	"os"
	"os/exec"
	"strings"
)

type Display struct {
	PNGPath string
	// EipsRun is overridable for tests. Defaults to /usr/sbin/eips.
	EipsRun func(args ...string) (string, error)
}

func (d *Display) eips() func(args ...string) (string, error) {
	if d.EipsRun != nil {
		return d.EipsRun
	}
	return func(args ...string) (string, error) {
		out, err := exec.Command("/usr/sbin/eips", args...).CombinedOutput()
		return strings.TrimSpace(string(out)), err
	}
}

func (d *Display) Show(png []byte) error {
	compatiblePNG, err := to8BitGrayscalePNG(png)
	if err != nil {
		return err
	}
	if err := os.WriteFile(d.PNGPath, compatiblePNG, 0644); err != nil {
		return err
	}
	out, err := d.eips()("-f", "-g", d.PNGPath)
	if err != nil {
		if out != "" {
			return fmt.Errorf("%w: %s", err, out)
		}
		return err
	}
	return nil
}

func to8BitGrayscalePNG(src []byte) ([]byte, error) {
	img, err := png.Decode(bytes.NewReader(src))
	if err != nil {
		return nil, fmt.Errorf("decode png: %w", err)
	}
	bounds := img.Bounds()
	gray := image.NewGray(bounds)
	for y := bounds.Min.Y; y < bounds.Max.Y; y++ {
		for x := bounds.Min.X; x < bounds.Max.X; x++ {
			gray.Set(x, y, color.GrayModel.Convert(img.At(x, y)))
		}
	}
	buf := &bytes.Buffer{}
	if err := png.Encode(buf, gray); err != nil {
		return nil, fmt.Errorf("encode grayscale png: %w", err)
	}
	return buf.Bytes(), nil
}
