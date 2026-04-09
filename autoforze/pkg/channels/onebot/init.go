package onebot

import (
	"github.com/sipeed/autoforze/pkg/bus"
	"github.com/sipeed/autoforze/pkg/channels"
	"github.com/sipeed/autoforze/pkg/config"
)

func init() {
	channels.RegisterFactory("onebot", func(cfg *config.Config, b *bus.MessageBus) (channels.Channel, error) {
		return NewOneBotChannel(cfg.Channels.OneBot, b)
	})
}
