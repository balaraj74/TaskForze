// AutoForze - Ultra-lightweight personal AI agent
// Inspired by and based on nanobot: https://github.com/HKUDS/nanobot
// License: MIT
//
// Copyright (c) 2026 AutoForze contributors

package main

import (
	"fmt"
	"os"
	"time"

	"github.com/spf13/cobra"

	"github.com/sipeed/autoforze/cmd/autoforze/internal"
	"github.com/sipeed/autoforze/cmd/autoforze/internal/agent"
	"github.com/sipeed/autoforze/cmd/autoforze/internal/auth"
	"github.com/sipeed/autoforze/cmd/autoforze/internal/cron"
	"github.com/sipeed/autoforze/cmd/autoforze/internal/gateway"
	"github.com/sipeed/autoforze/cmd/autoforze/internal/migrate"
	"github.com/sipeed/autoforze/cmd/autoforze/internal/model"
	"github.com/sipeed/autoforze/cmd/autoforze/internal/onboard"
	"github.com/sipeed/autoforze/cmd/autoforze/internal/skills"
	"github.com/sipeed/autoforze/cmd/autoforze/internal/status"
	"github.com/sipeed/autoforze/cmd/autoforze/internal/version"
	"github.com/sipeed/autoforze/pkg/config"
	"github.com/sipeed/autoforze/pkg/updater"
)

func NewAutoforzeCommand() *cobra.Command {
	short := fmt.Sprintf("%s autoforze - Personal AI Assistant %s\n\n", internal.Logo, config.GetVersion())

	cmd := &cobra.Command{
		Use:     "autoforze",
		Short:   short,
		Example: "autoforze version",
	}

	cmd.AddCommand(
		onboard.NewOnboardCommand(),
		agent.NewAgentCommand(),
		auth.NewAuthCommand(),
		gateway.NewGatewayCommand(),
		status.NewStatusCommand(),
		cron.NewCronCommand(),
		migrate.NewMigrateCommand(),
		skills.NewSkillsCommand(),
		model.NewModelCommand(),
		updater.NewUpdateCommand("autoforze"),
		version.NewVersionCommand(),
	)

	return cmd
}

const (
	colorBlue = "\033[1;38;2;62;93;185m"
	colorRed  = "\033[1;38;2;213;70;70m"
	banner    = "\r\n" +
		colorBlue + "██████╗ ██╗ ██████╗ ██████╗ " + colorRed + " ██████╗██╗      █████╗ ██╗    ██╗\n" +
		colorBlue + "██╔══██╗██║██╔════╝██╔═══██╗" + colorRed + "██╔════╝██║     ██╔══██╗██║    ██║\n" +
		colorBlue + "██████╔╝██║██║     ██║   ██║" + colorRed + "██║     ██║     ███████║██║ █╗ ██║\n" +
		colorBlue + "██╔═══╝ ██║██║     ██║   ██║" + colorRed + "██║     ██║     ██╔══██║██║███╗██║\n" +
		colorBlue + "██║     ██║╚██████╗╚██████╔╝" + colorRed + "╚██████╗███████╗██║  ██║╚███╔███╔╝\n" +
		colorBlue + "╚═╝     ╚═╝ ╚═════╝ ╚═════╝ " + colorRed + " ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝\n " +
		"\033[0m\r\n"
)

func main() {
	fmt.Printf("%s", banner)

	tz_env := os.Getenv("TZ")
	if tz_env != "" {
		fmt.Println("TZ environment:", tz_env)
		zoneinfo_env := os.Getenv("ZONEINFO")
		fmt.Println("ZONEINFO environment:", zoneinfo_env)
		loc, err := time.LoadLocation(tz_env)
		if err != nil {
			fmt.Println("Error loading time zone:", err)
		} else {
			fmt.Println("Time zone loaded successfully:", loc)
			time.Local = loc //nolint:gosmopolitan // We intentionally set local timezone from TZ env
		}
	}

	cmd := NewAutoforzeCommand()
	if err := cmd.Execute(); err != nil {
		os.Exit(1)
	}
}
