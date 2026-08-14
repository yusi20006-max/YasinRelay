package api

import (
	"log"
	"net/http"

	"fetcher/provider"
)

// imageFetcher is implemented by providers that can proxy an arbitrary
// image URL. Same type-assertion pattern as downloader in download.go.
type imageFetcher interface {
	FetchImage(rawURL string) ([]byte, string, error)
}

// Image streams an avatar/thumbnail image's raw bytes to the browser.
// Thumb/Avatar URLs from the parser point at *.translate.goog, which is
// blocked on many Iranian networks without a VPN — even though the page
// HTML loads fine, because that request happens server-side where the
// backend has unrestricted network access. Routing images through this
// endpoint means the browser only ever talks to our own server.
func Image(w http.ResponseWriter, r *http.Request) {

	rawURL := r.URL.Query().Get("u")
	if rawURL == "" {
		http.Error(w, "missing u parameter", http.StatusBadRequest)
		return
	}

	fetcher, ok := provider.Default.(imageFetcher)
	if !ok {
		http.Error(w, "image proxy not supported by active provider", http.StatusNotImplemented)
		return
	}

	body, contentType, err := fetcher.FetchImage(rawURL)
	if err != nil {
		log.Printf("image proxy FAILED for %s: %v", rawURL, err)
		http.Error(w, err.Error(), http.StatusBadGateway)
		return
	}
	log.Printf("image proxy OK for %s (%d bytes, %s)", rawURL, len(body), contentType)

	if contentType != "" {
		w.Header().Set("Content-Type", contentType)
	} else {
		w.Header().Set("Content-Type", "image/jpeg")
	}

	// Images are content-addressed by their signed translate.goog URL,
	// so it's safe to let the browser cache them for a while.
	w.Header().Set("Cache-Control", "public, max-age=86400")

	w.Write(body)

}
