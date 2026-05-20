package kindled

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestFetchDashboardPNG(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/dash/morning.png" || r.URL.Query().Get("device") != "kitchen" {
			t.Errorf("unexpected: %s %s", r.URL.Path, r.URL.RawQuery)
		}
		w.Header().Set("Content-Type", "image/png")
		w.Write([]byte("PNGDATA"))
	}))
	defer srv.Close()

	c := &Client{ServerURL: srv.URL, Dashboard: "morning", DeviceID: "kitchen"}
	body, err := c.FetchDashboard()
	if err != nil {
		t.Fatal(err)
	}
	if string(body) != "PNGDATA" {
		t.Errorf("body=%q", body)
	}
}

func TestPostTap(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/tap/morning" {
			t.Errorf("path=%s", r.URL.Path)
		}
		buf, _ := io.ReadAll(r.Body)
		s := string(buf)
		for _, want := range []string{`"device":"kitchen"`, `"x":42`, `"y":99`} {
			if !strings.Contains(s, want) {
				t.Errorf("body %q missing %q", s, want)
			}
		}
		w.Header().Set("Content-Type", "image/png")
		w.Write([]byte("TAPPNG"))
	}))
	defer srv.Close()

	c := &Client{ServerURL: srv.URL, Dashboard: "morning", DeviceID: "kitchen"}
	body, err := c.PostTap(42, 99)
	if err != nil {
		t.Fatal(err)
	}
	if string(body) != "TAPPNG" {
		t.Errorf("body=%q", body)
	}
}
