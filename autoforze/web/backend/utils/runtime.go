package utils

import (
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"

	"github.com/sipeed/autoforze/pkg/config"
	"github.com/sipeed/autoforze/pkg/logger"
)

// GetAutoforzeHome returns the autoforze home directory.
// Priority: $AUTOFORZE_HOME > ~/.autoforze
func GetAutoforzeHome() string {
	return config.GetHome()
}

// GetDefaultConfigPath returns the default path to the autoforze config file.
func GetDefaultConfigPath() string {
	if configPath := os.Getenv(config.EnvConfig); configPath != "" {
		return configPath
	}
	return filepath.Join(GetAutoforzeHome(), "config.json")
}

// FindAutoforzeBinary locates the autoforze executable.
// Search order:
//  1. AUTOFORZE_BINARY environment variable (explicit override)
//  2. Same directory as the current executable
//  3. Falls back to "autoforze" and relies on $PATH
func FindAutoforzeBinary() string {
	binaryName := "autoforze"
	if runtime.GOOS == "windows" {
		binaryName = "autoforze.exe"
	}

	if p := os.Getenv(config.EnvBinary); p != "" {
		if info, _ := os.Stat(p); info != nil && !info.IsDir() {
			return p
		}
	}

	if exe, err := os.Executable(); err == nil {
		logger.Debugf("Trying to find autoforze binary in %s", exe)
		candidate := filepath.Join(filepath.Dir(exe), binaryName)
		if info, err := os.Stat(candidate); err == nil && !info.IsDir() {
			return candidate
		}
	}

	return "autoforze"
}

// GetLocalIP returns the local IP address of the machine.
func GetLocalIP() string {
	addrs, err := net.InterfaceAddrs()
	if err != nil {
		return ""
	}
	for _, a := range addrs {
		if ipnet, ok := a.(*net.IPNet); ok && !ipnet.IP.IsLoopback() && ipnet.IP.To4() != nil {
			return ipnet.IP.String()
		}
	}
	return ""
}

// OpenBrowser automatically opens the given URL in the default browser.
func OpenBrowser(url string) error {
	switch runtime.GOOS {
	case "linux":
		return exec.Command("xdg-open", url).Start()
	case "windows":
		return exec.Command("rundll32", "url.dll,FileProtocolHandler", url).Start()
	case "darwin":
		return exec.Command("open", url).Start()
	default:
		return fmt.Errorf("unsupported platform")
	}
}
