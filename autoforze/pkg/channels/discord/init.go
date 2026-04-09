package discord

import (
	"github.com/sipeed/autoforze/pkg/audio/tts"
	"github.com/sipeed/autoforze/pkg/bus"
	"github.com/sipeed/autoforze/pkg/channels"
	"github.com/sipeed/autoforze/pkg/config"
)

func init() {
	channels.RegisterFactory("discord", func(cfg *config.Config, b *bus.MessageBus) (channels.Channel, error) {
		ch, err := NewDiscordChannel(cfg.Channels.Discord, b)
		if err == nil {
			ch.tts = tts.DetectTTS(cfg)
		}
		return ch, err
	})
}
