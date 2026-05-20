package kindled

import (
	"os"
	"path/filepath"
	"testing"
)

func writeConf(t *testing.T, body string) string {
	t.Helper()
	dir := t.TempDir()
	path := filepath.Join(dir, "k.conf")
	if err := os.WriteFile(path, []byte(body), 0644); err != nil {
		t.Fatal(err)
	}
	return path
}

func TestLoadConfigParsesAllFields(t *testing.T) {
	path := writeConf(t,
		"server_url=http://pi:8080\n"+
			"dashboard=morning\n"+
			"device_id=kitchen\n"+
			"poll_interval=60\n",
	)
	c, err := LoadConfig(path)
	if err != nil {
		t.Fatalf("LoadConfig: %v", err)
	}
	if c.ServerURL != "http://pi:8080" || c.Dashboard != "morning" ||
		c.DeviceID != "kitchen" || c.PollInterval != 60 {
		t.Errorf("got %+v", c)
	}
}

func TestLoadConfigTrimsWhitespaceAndIgnoresComments(t *testing.T) {
	path := writeConf(t,
		"# comment\n"+
			"  server_url =  http://pi:8080  \n"+
			"dashboard=m\n"+
			"device_id=k\n"+
			"poll_interval=10\n",
	)
	c, err := LoadConfig(path)
	if err != nil || c.ServerURL != "http://pi:8080" {
		t.Errorf("server_url=%q err=%v", c.ServerURL, err)
	}
}

func TestLoadConfigRequiresAllFields(t *testing.T) {
	path := writeConf(t, "server_url=http://x\n")
	if _, err := LoadConfig(path); err == nil {
		t.Errorf("expected missing-field error")
	}
}
