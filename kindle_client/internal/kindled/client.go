package kindled

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"
)

type Client struct {
	ServerURL string
	Dashboard string
	DeviceID  string
	HTTP      *http.Client // optional; defaults to a 10s-timeout client
}

func (c *Client) http() *http.Client {
	if c.HTTP != nil {
		return c.HTTP
	}
	return &http.Client{Timeout: 10 * time.Second}
}

func (c *Client) FetchDashboard() ([]byte, error) {
	u, _ := url.Parse(c.ServerURL + "/dash/" + c.Dashboard + ".png")
	q := u.Query()
	q.Set("device", c.DeviceID)
	u.RawQuery = q.Encode()
	resp, err := c.http().Get(u.String())
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("GET %s: %s", u, resp.Status)
	}
	return io.ReadAll(resp.Body)
}

type tapBody struct {
	Device string `json:"device"`
	X      int    `json:"x"`
	Y      int    `json:"y"`
}

func (c *Client) PostTap(x, y int) ([]byte, error) {
	body, _ := json.Marshal(tapBody{Device: c.DeviceID, X: x, Y: y})
	u := c.ServerURL + "/tap/" + c.Dashboard
	resp, err := c.http().Post(u, "application/json", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("POST %s: %s", u, resp.Status)
	}
	return io.ReadAll(resp.Body)
}
