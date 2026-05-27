package main

import (
	"flag"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/hanebambel/kindle-dashboard/kindle_client/internal/kindled"
)

func main() {
	cfgPath := flag.String("config", "/mnt/us/kindledashboard.conf", "config file")
	logPath := flag.String("log", "/tmp/kindledashboard.log", "log file (- for stderr)")
	flag.Parse()

	if *logPath != "-" {
		f, err := os.OpenFile(*logPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
		if err == nil {
			log.SetOutput(f)
			defer f.Close()
		}
	}

	cfg, err := kindled.LoadConfig(*cfgPath)
	if err != nil {
		log.Fatalf("config: %v", err)
	}
	client := &kindled.Client{
		ServerURL: cfg.ServerURL,
		Dashboard: cfg.Dashboard,
		DeviceID:  cfg.DeviceID,
	}
	disp := &kindled.Display{PNGPath: "/tmp/kindled-dash.png"}

	// Initial draw
	if png, err := client.FetchDashboard(); err == nil {
		if err := disp.Show(png); err != nil {
			log.Printf("initial display: %v", err)
		}
	} else {
		log.Printf("initial fetch failed: %v", err)
	}

	// Touch goroutine
	taps := make(chan kindled.Tap, 8)
	go func() {
		for {
			path, err := kindled.FindTouchscreen()
			if err != nil {
				log.Printf("find touchscreen: %v", err)
				time.Sleep(10 * time.Second)
				continue
			}
			f, err := os.Open(path)
			if err != nil {
				log.Printf("open %s: %v", path, err)
				time.Sleep(5 * time.Second)
				continue
			}
			if err := kindled.ReadTaps(f, taps); err != nil {
				log.Printf("read taps: %v", err)
			}
			time.Sleep(time.Second)
		}
	}()

	tick := time.NewTicker(time.Duration(cfg.PollInterval) * time.Second)
	defer tick.Stop()
	sigs := make(chan os.Signal, 1)
	signal.Notify(sigs, syscall.SIGTERM, syscall.SIGINT)

	for {
		select {
		case <-sigs:
			log.Printf("shutdown")
			return
		case <-tick.C:
			png, err := client.FetchDashboard()
			if err != nil {
				log.Printf("fetch: %v", err)
				continue
			}
			if err := disp.Show(png); err != nil {
				log.Printf("display: %v", err)
			}
		case tap := <-taps:
			png, err := client.PostTap(tap.X, tap.Y)
			if err != nil {
				log.Printf("tap post: %v", err)
				continue
			}
			if err := disp.Show(png); err != nil {
				log.Printf("display: %v", err)
			}
		}
	}
}
