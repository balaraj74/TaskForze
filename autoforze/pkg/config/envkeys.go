// AutoForze - Ultra-lightweight personal AI agent
// License: MIT
//
// Copyright (c) 2026 AutoForze contributors

package config

import (
	"os"
	"path/filepath"

	"github.com/sipeed/autoforze/pkg"
)

// Runtime environment variable keys for the autoforze process.
// These control the location of files and binaries at runtime and are read
// directly via os.Getenv / os.LookupEnv. All autoforze-specific keys use the
// AUTOFORZE_ prefix. Reference these constants instead of inline string
// literals to keep all supported knobs visible in one place and to prevent
// typos.
const (
	// EnvHome overrides the base directory for all autoforze data
	// (config, workspace, skills, auth store, …).
	// Default: ~/.autoforze
	EnvHome = "AUTOFORZE_HOME"

	// EnvConfig overrides the full path to the JSON config file.
	// Default: $AUTOFORZE_HOME/config.json
	EnvConfig = "AUTOFORZE_CONFIG"

	// EnvBuiltinSkills overrides the directory from which built-in
	// skills are loaded.
	// Default: <cwd>/skills
	EnvBuiltinSkills = "AUTOFORZE_BUILTIN_SKILLS"

	// EnvBinary overrides the path to the autoforze executable.
	// Used by the web launcher when spawning the gateway subprocess.
	// Default: resolved from the same directory as the current executable.
	EnvBinary = "AUTOFORZE_BINARY"

	// EnvGatewayHost overrides the host address for the gateway server.
	// Default: "127.0.0.1"
	EnvGatewayHost = "AUTOFORZE_GATEWAY_HOST"
)

func GetHome() string {
	homePath, _ := os.UserHomeDir()
	if autoforzeHome := os.Getenv(EnvHome); autoforzeHome != "" {
		homePath = autoforzeHome
	} else if homePath != "" {
		homePath = filepath.Join(homePath, pkg.DefaultAutoForzeHome)
	}
	if homePath == "" {
		homePath = "."
	}
	return homePath
}
