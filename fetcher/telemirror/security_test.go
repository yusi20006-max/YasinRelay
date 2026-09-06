package telemirror

import (
	"context"
	"net"
	"net/http"
	neturl "net/url"
	"strings"
	"testing"
	"time"
)

func stubLookup(addrs []net.IPAddr, err error) func() {
	orig := lookupIPAddr
	lookupIPAddr = func(ctx context.Context, host string) ([]net.IPAddr, error) {
		return addrs, err
	}
	return func() { lookupIPAddr = orig }
}

func ipAddrs(ss ...string) []net.IPAddr {
	out := make([]net.IPAddr, 0, len(ss))
	for _, s := range ss {
		out = append(out, net.IPAddr{IP: net.ParseIP(s)})
	}
	return out
}

func TestResolveValidatedIPsPublicIPAccepted(t *testing.T) {
	ctx := context.Background()
	for _, host := range []string{"8.8.8.8", "1.1.1.1", "142.250.72.14", "2001:4860:4860::8888"} {
		ips, err := resolveValidatedIPs(ctx, host)
		if err != nil {
			t.Errorf("resolveValidatedIPs(%q) unexpected error: %v", host, err)
			continue
		}
		if len(ips) != 1 {
			t.Errorf("resolveValidatedIPs(%q) = %d ips, want 1", host, len(ips))
		}
	}
}

func TestResolveValidatedIPsForbiddenIPRejected(t *testing.T) {
	ctx := context.Background()
	forbidden := []string{
		"127.0.0.1", "::1",
		"10.0.0.1", "172.16.0.1", "172.31.255.255", "192.168.1.1",
		"169.254.10.20", "fe80::1",
		"fc00::1", "fd00::1", // ULA
		"::", "0.0.0.0",
		"224.0.0.1", "ff02::1", // multicast
		"100.64.0.1",                               // CGNAT
		"192.0.2.1", "198.51.100.1", "203.0.113.1", // TEST-NET
		"198.18.0.1", // benchmarking
		"240.0.0.1",  // reserved
		"255.255.255.255",
		"::ffff:127.0.0.1", // 4-in-6 loopback smuggling
		"::ffff:10.0.0.1",  // 4-in-6 private smuggling
	}
	for _, host := range forbidden {
		if _, err := resolveValidatedIPs(ctx, host); err == nil {
			t.Errorf("resolveValidatedIPs(%q) = success, want rejection", host)
		}
	}
}

func TestResolveValidatedIPsLocalhostRejected(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	// Fail closed either way: loopback answer => forbidden, or lookup
	// failure => rejected. Both are acceptable rejections.
	if _, err := resolveValidatedIPs(ctx, "localhost"); err == nil {
		t.Errorf("resolveValidatedIPs(localhost) = success, want rejection")
	}
}

func TestResolveValidatedIPsPublicHostnameAccepted(t *testing.T) {
	restore := stubLookup(ipAddrs("93.184.216.34"), nil) // example.com
	defer restore()
	ctx := context.Background()
	ips, err := resolveValidatedIPs(ctx, "public.example")
	if err != nil {
		t.Fatalf("resolveValidatedIPs(public hostname) unexpected error: %v", err)
	}
	if len(ips) != 1 || ips[0].String() != "93.184.216.34" {
		t.Fatalf("unexpected ips: %v", ips)
	}
}

func TestResolveValidatedIPsMixedAnswersFailClosed(t *testing.T) {
	ctx := context.Background()
	cases := [][]string{
		{"93.184.216.34", "192.168.1.1"},
		{"93.184.216.34", "127.0.0.1"},
		{"93.184.216.34", "10.0.0.5"},
		{"93.184.216.34", "::1"},
		{"93.184.216.34", "169.254.1.1"},
		{"93.184.216.34", "224.0.0.1"},
		{"93.184.216.34", "::"},
	}
	for _, addrs := range cases {
		restore := stubLookup(ipAddrs(addrs...), nil)
		_, err := resolveValidatedIPs(ctx, "mixed.example")
		restore()
		if err == nil {
			t.Errorf("resolveValidatedIPs(mixed %v) = success, want fail-closed rejection", addrs)
		}
	}
}

func TestValidateSafeURL(t *testing.T) {
	ctx := context.Background()
	// Public IP literal accepted without DNS.
	if _, err := validateSafeURL(ctx, "https://8.8.8.8/s/x"); err != nil {
		t.Errorf("validateSafeURL(public IP) unexpected error: %v", err)
	}
	// Forbidden IP literals rejected.
	for _, raw := range []string{
		"https://127.0.0.1/s/x",
		"https://192.168.1.1/",
		"https://10.0.0.1/",
		"https://[::1]/",
		"https://[fc00::1]/",
		"https://0.0.0.0/",
	} {
		if _, err := validateSafeURL(ctx, raw); err == nil {
			t.Errorf("validateSafeURL(%q) = success, want rejection", raw)
		}
	}
	// Non-https rejected.
	if _, err := validateSafeURL(ctx, "http://8.8.8.8/"); err == nil {
		t.Errorf("validateSafeURL(http) = success, want rejection")
	}
	// Localhost rejected (real resolver, fail closed).
	func() {
		c, cancel := context.WithTimeout(ctx, 5*time.Second)
		defer cancel()
		if _, err := validateSafeURL(c, "https://localhost/"); err == nil {
			t.Errorf("validateSafeURL(localhost) = success, want rejection")
		}
	}()
	// Public hostname accepted via stubbed resolver.
	restore := stubLookup(ipAddrs("93.184.216.34"), nil)
	if _, err := validateSafeURL(ctx, "https://public.example/x"); err != nil {
		t.Errorf("validateSafeURL(public hostname) unexpected error: %v", err)
	}
	restore()
	// Mixed answers rejected via stubbed resolver.
	restore = stubLookup(ipAddrs("93.184.216.34", "192.168.1.1"), nil)
	if _, err := validateSafeURL(ctx, "https://mixed.example/x"); err == nil {
		t.Errorf("validateSafeURL(mixed) = success, want rejection")
	}
	restore()
}

func TestDirectDialRejectsPrivateBeforeContact(t *testing.T) {
	direct := proxyAttempt{ip: "", sni: sniUseHost, fp: fingerprints[1]}
	for _, addr := range []string{
		"192.168.1.1:443", "10.0.0.1:443", "127.0.0.1:443", "[::1]:443",
		"[fc00::1]:443", "0.0.0.0:443",
	} {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		start := time.Now()
		_, err := dialTLSFor(direct, "irrelevant.example")(ctx, "tcp", addr)
		elapsed := time.Since(start)
		cancel()
		if err == nil {
			t.Errorf("direct dial(%q) = success, want rejection", addr)
			continue
		}
		if !strings.Contains(strings.ToLower(err.Error()), "forbidden") {
			t.Errorf("direct dial(%q) error %q does not mention forbidden (must fail in validation, before TCP contact)", addr, err)
		}
		if elapsed > 4*time.Second {
			t.Errorf("direct dial(%q) took %v, expected fast validation failure before network contact", addr, elapsed)
		}
	}
	// Hostname whose DNS answer is private must also be rejected before
	// any TCP contact, even though the name itself looks innocuous.
	restore := stubLookup(ipAddrs("10.1.2.3"), nil)
	defer restore()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_, err := dialTLSFor(direct, "evil.example")(ctx, "tcp", "evil.example:443")
	if err == nil {
		t.Fatalf("direct dial(evil.example -> 10.x) = success, want rejection")
	}
	if !strings.Contains(strings.ToLower(err.Error()), "forbidden") {
		t.Fatalf("direct dial(evil.example) error %q does not mention forbidden", err)
	}
}

func TestFixedIPFrontedPathUnchanged(t *testing.T) {
	// Pinned front attempts must still exist.
	found := false
	for _, ap := range proxyAttempts {
		if ap.ip != "" {
			found = true
			break
		}
	}
	if !found {
		t.Fatalf("no fixed-IP fronted attempts in proxyAttempts")
	}
	// The fixed-IP path must not consult the hostname resolver: it dials
	// the pinned IP. Stub the resolver to fail loudly if called.
	called := false
	orig := lookupIPAddr
	lookupIPAddr = func(ctx context.Context, host string) ([]net.IPAddr, error) {
		called = true
		return nil, context.DeadlineExceeded
	}
	defer func() { lookupIPAddr = orig }()
	// Dial a loopback fixed IP with nothing listening: expect a fast
	// connection-refused (proof it targeted the fixed IP), NOT a
	// validation error, and the resolver must not have been called.
	fixed := proxyAttempt{ip: "127.0.0.1", sni: frontSNI, fp: fingerprints[1]}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_, err := dialTLSFor(fixed, "anything.example")(ctx, "tcp", "anything.example:443")
	if err == nil {
		t.Fatalf("fixed-IP dial unexpectedly succeeded")
	}
	if called {
		t.Errorf("fixed-IP path called DNS resolver; must dial pinned IP without hostname resolution")
	}
	if strings.Contains(strings.ToLower(err.Error()), "forbidden") {
		t.Errorf("fixed-IP path returned validation error %q; must preserve direct dial to pinned IP", err)
	}
}

func TestSafeCheckRedirectPreserved(t *testing.T) {
	// Public redirect target accepted (stubbed).
	restore := stubLookup(ipAddrs("93.184.216.34"), nil)
	req := &http.Request{URL: mustParseURL(t, "https://public.example/next"), Method: "GET"}
	req = req.WithContext(context.Background())
	if err := safeCheckRedirect(req, nil); err != nil {
		t.Errorf("safeCheckRedirect(public) unexpected error: %v", err)
	}
	restore()
	// Private redirect target rejected without stub (IP literal, no DNS).
	reqPriv := &http.Request{URL: mustParseURL(t, "https://192.168.1.1/next"), Method: "GET"}
	reqPriv = reqPriv.WithContext(context.Background())
	if err := safeCheckRedirect(reqPriv, nil); err == nil {
		t.Errorf("safeCheckRedirect(private) = success, want rejection")
	}
	// Localhost redirect rejected.
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	reqLocal := &http.Request{URL: mustParseURL(t, "https://localhost/next"), Method: "GET"}
	reqLocal = reqLocal.WithContext(ctx)
	if err := safeCheckRedirect(reqLocal, nil); err == nil {
		t.Errorf("safeCheckRedirect(localhost) = success, want rejection")
	}
	// Mixed-answer redirect rejected.
	restore = stubLookup(ipAddrs("93.184.216.34", "10.0.0.1"), nil)
	reqMixed := &http.Request{URL: mustParseURL(t, "https://mixed.example/next"), Method: "GET"}
	reqMixed = reqMixed.WithContext(context.Background())
	if err := safeCheckRedirect(reqMixed, nil); err == nil {
		t.Errorf("safeCheckRedirect(mixed) = success, want rejection")
	}
	restore()
	// Redirect cap preserved.
	restore = stubLookup(ipAddrs("93.184.216.34"), nil)
	defer restore()
	reqCap := &http.Request{URL: mustParseURL(t, "https://public.example/next"), Method: "GET"}
	reqCap = reqCap.WithContext(context.Background())
	via := make([]*http.Request, 10)
	if err := safeCheckRedirect(reqCap, via); err == nil {
		t.Errorf("safeCheckRedirect(10 redirects) = success, want stop")
	}
}

func mustParseURL(t *testing.T, s string) *neturl.URL {
	t.Helper()
	u, err := neturl.Parse(s)
	if err != nil {
		t.Fatalf("parse %q: %v", s, err)
	}
	return u
}

func TestFetchURLLimitRejectsPrivateBeforeContact(t *testing.T) {
	c := NewClient()
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	start := time.Now()
	_, _, err := c.FetchURLLimit(ctx, "https://192.168.1.1/file", 1024)
	if err == nil {
		t.Fatalf("FetchURLLimit(private) = success, want rejection")
	}
	if time.Since(start) > 8*time.Second {
		t.Errorf("FetchURLLimit(private) took too long; must reject before network contact")
	}
}
