package provider

type Provider interface {
	LoadChannel(name string) ([]byte, error)
}

var Default Provider
