package vk

import (
	"github.com/sipeed/autoforze/pkg/bus"
	"github.com/sipeed/autoforze/pkg/channels"
	"github.com/sipeed/autoforze/pkg/config"
)

func init() {
	channels.RegisterFactory("vk", func(cfg *config.Config, b *bus.MessageBus) (channels.Channel, error) {
		return NewVKChannel(cfg, b)
	})
}
