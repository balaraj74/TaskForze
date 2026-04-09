package teamswebhook

import (
	"github.com/sipeed/autoforze/pkg/bus"
	"github.com/sipeed/autoforze/pkg/channels"
	"github.com/sipeed/autoforze/pkg/config"
)

func init() {
	channels.RegisterFactory("teams_webhook", func(cfg *config.Config, b *bus.MessageBus) (channels.Channel, error) {
		return NewTeamsWebhookChannel(cfg.Channels.TeamsWebhook, b)
	})
}
