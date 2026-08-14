package api

import (
	"net/http"
	"regexp"

	"fetcher/provider"
)

// downloader is implemented by providers that can proxy an arbitrary
// media URL (not just the channel widget HTML). Type-asserted rather
// than added to the Provider interface so the older/simpler providers
// (direct.go, google.go, google_translate.go) don't need to grow a
// method they never use.
type downloader interface {
	FetchDownload(rawURL string) ([]byte, string, error)
}

var unsafeFilenameChars = regexp.MustCompile(`[^\w\-. ]+`)

func sanitizeFilename(name string) string {
	if name == "" {
		return "file"
	}
	clean := unsafeFilenameChars.ReplaceAllString(name, "_")
	if len(clean) > 120 {
		clean = clean[:120]
	}
	return clean
}

// Download streams a video/audio/document's raw bytes to the browser as
// a normal file download. The frontend never fetches translate.goog URLs
// directly for these (only images use a plain <img src>) since a proper
// file download needs Content-Disposition and, for anything sizeable,
// the same domain-fronted path used everywhere else.
func Download(w http.ResponseWriter, r *http.Request) {

	rawURL := r.URL.Query().Get("u")
	if rawURL == "" {
		http.Error(w, "missing u parameter", http.StatusBadRequest)
		return
	}

	dl, ok := provider.Default.(downloader)
	if !ok {
		http.Error(w, "download not supported by active provider", http.StatusNotImplemented)
		return
	}

	body, contentType, err := dl.FetchDownload(rawURL)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadGateway)
		return
	}

	if contentType != "" {
		w.Header().Set("Content-Type", contentType)
	} else {
		w.Header().Set("Content-Type", "application/octet-stream")
	}

	name := sanitizeFilename(r.URL.Query().Get("name"))
	w.Header().Set("Content-Disposition", `attachment; filename="`+name+`"`)

	w.Write(body)

}
