package slack

import (
	"github.com/sipeed/autoforze/pkg/bus"
	"github.com/sipeed/autoforze/pkg/channels"
	"github.com/sipeed/autoforze/pkg/config"
)

func init() {
	channels.RegisterFactory("slack", func(cfg *config.Config, b *bus.MessageBus) (channels.Channel, error) {
		return NewSlackChannel(cfg.Channels.Slack, b)
	})
}
