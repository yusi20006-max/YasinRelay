package api

import (
	"encoding/json"
	"net/http"
	"strings"

	"fetcher/parser"
	"fetcher/provider"
	"fetcher/telemirror"
)

func Channel(w http.ResponseWriter, r *http.Request) {

	name := strings.TrimPrefix(r.URL.Path, "/api/channel/")

	html, err := provider.Default.LoadChannel(name)
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}

	ch, posts, err := telemirror.ParseHTML(string(html))
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}

	channel := parser.Convert(ch, posts)

	w.Header().Set("Content-Type", "application/json")

	json.NewEncoder(w).Encode(channel)

}
