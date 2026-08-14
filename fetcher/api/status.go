package api

import (
	"encoding/json"
	"net/http"
	"time"

	"fetcher/provider"
)

type StatusResponse struct {
	Connected bool   `json:"connected"`
	Ms        int64  `json:"ms"`
	Error     string `json:"error,omitempty"`
}

// probeChannel is a well-known, always-public channel used only to test
// whether the active provider can currently reach Telegram. Its content
// is discarded.
const probeChannel = "telegram"

// Status performs a real fetch against the active provider so the
// frontend can show whether the anti-censorship connection is actually
// working right now, not just whether the local server is up.
func Status(w http.ResponseWriter, r *http.Request) {

	start := time.Now()

	_, err := provider.Default.LoadChannel(probeChannel)

	elapsed := time.Since(start).Milliseconds()

	w.Header().Set("Content-Type", "application/json")

	if err != nil {

		json.NewEncoder(w).Encode(StatusResponse{
			Connected: false,
			Ms:        elapsed,
			Error:     err.Error(),
		})

		return

	}

	json.NewEncoder(w).Encode(StatusResponse{
		Connected: true,
		Ms:        elapsed,
	})

}
