package kindled

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
	"strings"
)

type Config struct {
	ServerURL    string
	Dashboard    string
	DeviceID     string
	PollInterval int
}

func LoadConfig(path string) (Config, error) {
	f, err := os.Open(path)
	if err != nil {
		return Config{}, err
	}
	defer f.Close()

	c := Config{}
	scan := bufio.NewScanner(f)
	for scan.Scan() {
		line := strings.TrimSpace(scan.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		k, v, ok := strings.Cut(line, "=")
		if !ok {
			continue
		}
		k = strings.TrimSpace(k)
		v = strings.TrimSpace(v)
		switch k {
		case "server_url":
			c.ServerURL = v
		case "dashboard":
			c.Dashboard = v
		case "device_id":
			c.DeviceID = v
		case "poll_interval":
			n, err := strconv.Atoi(v)
			if err != nil {
				return c, fmt.Errorf("poll_interval not an int: %v", v)
			}
			c.PollInterval = n
		}
	}
	if err := scan.Err(); err != nil {
		return c, err
	}
	if c.ServerURL == "" || c.Dashboard == "" || c.DeviceID == "" || c.PollInterval == 0 {
		return c, fmt.Errorf("config missing required fields: %+v", c)
	}
	return c, nil
}
