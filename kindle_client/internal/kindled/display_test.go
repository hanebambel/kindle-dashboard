package kindled

import (
	"os"
	"path/filepath"
	"testing"
)

func TestDisplayWritesPNGAndRunsEips(t *testing.T) {
	dir := t.TempDir()
	pngPath := filepath.Join(dir, "dash.png")
	eipsArgs := [][]string{}

	d := &Display{
		PNGPath: pngPath,
		EipsRun: func(args ...string) error {
			eipsArgs = append(eipsArgs, args)
			return nil
		},
	}
	if err := d.Show([]byte("PNG-BYTES")); err != nil {
		t.Fatal(err)
	}
	got, _ := os.ReadFile(pngPath)
	if string(got) != "PNG-BYTES" {
		t.Errorf("png=%q", got)
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
