package provider

import (
	"context"

	"fetcher/telemirror"
)

type TeleMirror struct {
	client *telemirror.Client
}

func NewTeleMirror() *TeleMirror {

	return &TeleMirror{

		client: telemirror.NewClient(),
	}

}

// LoadChannel fetches the raw HTML widget for a channel through the
// telemirror engine (Google Translate domain-fronting + utls fingerprint).
func (t *TeleMirror) LoadChannel(name string) ([]byte, error) {

	html, err := t.client.FetchHTML(context.Background(), name)
	if err != nil {
		return nil, err
	}

	return []byte(html), nil

}

// FetchDownload proxies an arbitrary media URL (video/audio/document)
// through the same domain-fronting path used for the channel widget,
// sized for large files rather than the small image/thumbnail cap.
func (t *TeleMirror) FetchDownload(rawURL string) ([]byte, string, error) {

	return t.client.FetchDownload(context.Background(), rawURL)

}
