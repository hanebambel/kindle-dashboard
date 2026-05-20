package kindled

import (
	"os"
	"os/exec"
)

type Display struct {
	PNGPath string
	// EipsRun is overridable for tests. Defaults to /usr/sbin/eips.
	EipsRun func(args ...string) error
}

func (d *Display) eips() func(args ...string) error {
	if d.EipsRun != nil {
		return d.EipsRun
	}
	return func(args ...string) error {
		return exec.Command("/usr/sbin/eips", args...).Run()
	}
}

func (d *Display) Show(png []byte) error {
	if err := os.WriteFile(d.PNGPath, png, 0644); err != nil {
		return err
	}
	return d.eips()("-f", "-g", d.PNGPath)
}
