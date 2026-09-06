package telemirror

// SSRF / DNS-rebinding hardening for the Telemirror direct-dial path.
//
// Synchronization note: this file is kept behaviorally identical in
//   - Openfeed:                 internal/telemirror/security.go
//   - YasinRelay/fetcher:       fetcher/telemirror/security.go
// Any security change here must be ported to the other copy so both
// implementations stay behaviorally equivalent. See docs note in the
// fix commit / SECURITY_SYNC comment below.
//
// Threat model (P1): the direct dial path (proxyAttempt with ip == "")
// previously let net.Dialer resolve the hostname again at use time,
// after any check-time validation. An attacker controlling DNS (or a
// victim URL whose DNS flips between check and use) could rebind the
// hostname to a loopback/private/link-local/multicast/unspecified
// address (DNS rebinding TOCTOU) and reach internal services. Fail closed.
//
// Fix:
//   - resolveValidatedIPs resolves once and rejects forbidden answers.
//   - validateSafeURL pre-checks user-supplied URLs (early fail, before
//     any TCP contact to the target).
//   - dialTLSFor re-resolves inside the actual dial closure and dials
//     only the validated IP literals, never passing a hostname to
//     net.Dialer (TOCTOU pinning).
//   - safeCheckRedirect re-validates every redirect target (fail closed).
// Fixed-IP fronted attempts (ap.ip != "") are preserved unchanged:
// they keep dialing the pinned front IP.

import (
	"context"
	"fmt"
	"net"
	"net/http"
	neturl "net/url"
	"strings"
)

// forbiddenNets are special-use ranges rejected in addition to the
// net.IP method checks (loopback, private, link-local, multicast,
// unspecified). Listed explicitly so the filter fails closed even if
// a Go release changes the semantics of IsPrivate/IsGlobalUnicast.
var forbiddenNets []*net.IPNet

func init() {
	for _, cidr := range []string{
		"0.0.0.0/8",       // software scope ("0." prefix)
		"10.0.0.0/8",      // RFC1918 (also covered by IsPrivate)
		"100.64.0.0/10",   // CGNAT
		"127.0.0.0/8",     // loopback (also covered by IsLoopback)
		"169.254.0.0/16",  // link-local (also covered by IsLinkLocalUnicast)
		"172.16.0.0/12",   // RFC1918 (also covered by IsPrivate)
		"192.0.0.0/24",    // IETF protocol assignments
		"192.0.2.0/24",    // TEST-NET-1
		"192.168.0.0/16",  // RFC1918 (also covered by IsPrivate)
		"198.18.0.0/15",   // benchmarking
		"198.51.100.0/24", // TEST-NET-2
		"203.0.113.0/24",  // TEST-NET-3
		"224.0.0.0/4",     // multicast (also covered by IsMulticast)
		"240.0.0.0/4",     // reserved
		"255.255.255.255/32",
		"::/128",       // unspecified (also covered by IsUnspecified)
		"::1/128",      // loopback (also covered by IsLoopback)
		"64:ff9b::/96", // IPv4/IPv6 translation
		"100::/64",     // discard
		"2001::/32",    // Teredo (embeds IPv4, tunnel risk)
		"2002::/16",    // 6to4 (embeds IPv4, tunnel risk)
		"fc00::/7",     // unique-local (also covered by IsPrivate)
		"fe80::/10",    // link-local (also covered by IsLinkLocalUnicast)
		"ff00::/8",     // multicast (also covered by IsMulticast)
	} {
		_, n, err := net.ParseCIDR(cidr)
		if err != nil {
			panic(fmt.Sprintf("telemirror: bad forbidden CIDR %q: %v", cidr, err))
		}
		forbiddenNets = append(forbiddenNets, n)
	}
}

// isForbiddenIP reports whether ip must never be dialed/fetched.
// Fail closed: nil is forbidden.
func isForbiddenIP(ip net.IP) bool {
	if ip == nil {
		return true
	}
	if ip.IsUnspecified() || ip.IsLoopback() || ip.IsMulticast() {
		return true
	}
	if ip.IsLinkLocalUnicast() || ip.IsLinkLocalMulticast() {
		return true
	}
	if ip.IsPrivate() {
		return true
	}
	for _, n := range forbiddenNets {
		if n.Contains(ip) {
			return true
		}
	}
	// Evaluate an embedded IPv4 too (e.g. ::ffff:127.0.0.1), so a
	// 4-in-6 encoding cannot smuggle a forbidden v4 destination past
	// the checks above.
	if v4 := ip.To4(); v4 != nil && !ip.IsUnspecified() {
		for _, n := range forbiddenNets {
			if n.Contains(v4) {
				return true
			}
		}
		if v4.IsUnspecified() || v4.IsLoopback() || v4.IsMulticast() || v4.IsPrivate() || v4.IsLinkLocalUnicast() || v4.IsLinkLocalMulticast() {
			return true
		}
	}
	return false
}

// lookupIPAddr is the DNS lookup hook. It defaults to the system
// resolver but is a variable so regression tests can stub mixed or
// public answers deterministically without live network access.
var lookupIPAddr = func(ctx context.Context, host string) ([]net.IPAddr, error) {
	return net.DefaultResolver.LookupIPAddr(ctx, host)
}

// resolveValidatedIPs resolves host once and returns only validated,
// dialable IPs. Fail closed:
//   - IP literals: rejected when forbidden, otherwise returned as-is.
//   - Hostnames: resolved via LookupIPAddr; rejected when the lookup
//     fails, returns no answers, or ANY answer is forbidden (single
//     poisoned answer poisons the whole set — required against DNS
//     rebinding where the attacker controls one record).
func resolveValidatedIPs(ctx context.Context, host string) ([]net.IP, error) {
	host = strings.TrimSpace(host)
	host = strings.TrimSuffix(host, ".")
	if host == "" {
		return nil, fmt.Errorf("telemirror: empty host")
	}
	if ip := net.ParseIP(host); ip != nil {
		if isForbiddenIP(ip) {
			return nil, fmt.Errorf("telemirror: forbidden IP %q", host)
		}
		return []net.IP{ip}, nil
	}
	addrs, err := lookupIPAddr(ctx, host)
	if err != nil {
		return nil, fmt.Errorf("telemirror: DNS lookup failed for %q: %w", host, err)
	}
	if len(addrs) == 0 {
		return nil, fmt.Errorf("telemirror: no DNS answers for %q", host)
	}
	out := make([]net.IP, 0, len(addrs))
	for _, a := range addrs {
		ip := a.IP
		if ip == nil {
			return nil, fmt.Errorf("telemirror: empty DNS answer for %q", host)
		}
		if isForbiddenIP(ip) {
			return nil, fmt.Errorf("telemirror: forbidden DNS answer %s for %q", ip.String(), host)
		}
		out = append(out, ip)
	}
	return out, nil
}

// validateSafeURL parses rawURL, requires https with a non-empty host,
// and validates the hostname via resolveValidatedIPs. It is the
// check-time gate; the dial-time gate inside dialTLSFor re-validates
// and pins the connection to validated IPs so check and use cannot
// diverge (DNS rebinding TOCTOU).
func validateSafeURL(ctx context.Context, rawURL string) (*neturl.URL, error) {
	u, err := neturl.Parse(rawURL)
	if err != nil {
		return nil, fmt.Errorf("telemirror: bad url: %w", err)
	}
	if u.Scheme != "https" {
		return nil, fmt.Errorf("telemirror: forbidden scheme %q", u.Scheme)
	}
	if u.Host == "" {
		return nil, fmt.Errorf("telemirror: empty host")
	}
	hostname := u.Hostname()
	if hostname == "" {
		return nil, fmt.Errorf("telemirror: empty hostname")
	}
	if _, err := resolveValidatedIPs(ctx, hostname); err != nil {
		return nil, err
	}
	return u, nil
}

// safeCheckRedirect is installed as http.Client.CheckRedirect so every
// redirect target is re-validated. Any forbidden/private/rebound target
// aborts the redirect chain (fail closed). The 10-redirect cap preserves
// net/http's default behavior.
func safeCheckRedirect(req *http.Request, via []*http.Request) error {
	if len(via) >= 10 {
		return fmt.Errorf("telemirror: stopped after 10 redirects")
	}
	if req == nil || req.URL == nil {
		return fmt.Errorf("telemirror: invalid redirect")
	}
	if _, err := validateSafeURL(req.Context(), req.URL.String()); err != nil {
		return err
	}
	return nil
}
