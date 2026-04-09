package matrix

import (
	"path/filepath"

	"github.com/sipeed/autoforze/pkg/bus"
	"github.com/sipeed/autoforze/pkg/channels"
	"github.com/sipeed/autoforze/pkg/config"
)

func init() {
	channels.RegisterFactory("matrix", func(cfg *config.Config, b *bus.MessageBus) (channels.Channel, error) {
		matrixCfg := cfg.Channels.Matrix
		cryptoDatabasePath := matrixCfg.CryptoDatabasePath
		if cryptoDatabasePath == "" {
			cryptoDatabasePath = filepath.Join(cfg.WorkspacePath(), "matrix")
		}
		return NewMatrixChannel(matrixCfg, b, cryptoDatabasePath)
	})
}
