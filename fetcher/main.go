package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"net/http/cookiejar"
	"os"
	"regexp"
	"strings"
	"time"
)

type Post struct {
	MessageID string `json:"message_id"`
	Text      string `json:"text"`
	MediaURL  string `json:"media_url,omitempty"`
}

var telescopeRegex = regexp.MustCompile(`https?://[^\x60'\"\\)\s>]*telesco\.pe[^\x60'\"\\)\s>]*`)

func findTelescopeURL(s string) string {
	s = strings.ReplaceAll(s, "&quot;", "\"")
	match := telescopeRegex.FindString(s)
	if match != "" {
		match = strings.Trim(match, `'"()`)
		match = strings.ReplaceAll(match, "&amp;", "&")
		return match
	}
	return ""
}

func findDivEnd(s string) int {
	balance := 1
	i := 0
	n := len(s)
	for i < n {
		if i+4 <= n && strings.ToLower(s[i:i+4]) == "<div" {
			if i+4 == n || s[i+4] == ' ' || s[i+4] == '>' {
				balance++
			}
			i += 4
		} else if i+6 <= n && strings.ToLower(s[i:i+6]) == "</div>" {
			balance--
			if balance == 0 {
				return i
			}
			i += 6
		} else {
			i++
		}
	}
	return -1
}

func extractMediaURL(segment string) string {
	targets := []string{"tgme_widget_message_photo_wrap", "tgme_widget_message_video_player", "tgme_widget_message_video_thumb", "tgme_widget_message_inline_image"}
	for _, target := range targets {
		idx := strings.Index(segment, target)
		if idx != -1 {
			url := findTelescopeURL(segment[idx:])
			if url != "" {
				return url
			}
		}
	}

	cleanSegment := segment
	userPhotoIdx := strings.Index(segment, "tgme_widget_message_user_photo")
	if userPhotoIdx != -1 {
		cleanSegment = segment[userPhotoIdx+30:]
		endDiv := findDivEnd(cleanSegment)
		if endDiv != -1 {
			cleanSegment = cleanSegment[endDiv:]
		}
	}
	return findTelescopeURL(cleanSegment)
}

func frontURL(urlStr string) string {
	if urlStr == "" {
		return ""
	}
	re := regexp.MustCompile(`(https?://)(cdn[0-9]*)\.telesco\.pe(/.*)?`)
	if re.MatchString(urlStr) {
		return re.ReplaceAllString(urlStr, `${1}${2}-telesco-pe.translate.goog${3}`)
	}
	reGeneral := regexp.MustCompile(`(https?://)telesco\.pe(/.*)?`)
	if reGeneral.MatchString(urlStr) {
		return reGeneral.ReplaceAllString(urlStr, `${1}telesco-pe.translate.goog${2}`)
	}
	return urlStr
}

func cleanHTMLText(htmlStr string) string {
	rBr := regexp.MustCompile(`(?i)<br\s*/?>`)
	text := rBr.ReplaceAllString(htmlStr, "\n")

	rTags := regexp.MustCompile(`<[^>]*>`)
	text = rTags.ReplaceAllString(text, "")

	text = strings.ReplaceAll(text, "&amp;", "&")
	text = strings.ReplaceAll(text, "&lt;", "<")
	text = strings.ReplaceAll(text, "&gt;", ">")
	text = strings.ReplaceAll(text, "&quot;", "\"")
	text = strings.ReplaceAll(text, "&#39;", "'")
	text = strings.ReplaceAll(text, "&nbsp;", " ")

	return strings.TrimSpace(text)
}

func createHTTPClient() (*http.Client, error) {
	jar, err := cookiejar.New(nil)
	if err != nil {
		return nil, err
	}
	return &http.Client{
		Timeout: 15 * time.Second,
		Jar:     jar,
	}, nil
}

func sendHTTPRequest(client *http.Client, urlStr string, hostHeader string) (string, error) {
	req, err := http.NewRequest("GET", urlStr, nil)
	if err != nil {
		return "", fmt.Errorf("failed to create request: %w", err)
	}

	// Browser-like headers
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
	req.Header.Set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8")
	req.Header.Set("Accept-Language", "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7")
	req.Header.Set("Referer", "https://translate.google.com/")
	req.Header.Set("Connection", "keep-alive")

	if hostHeader != "" {
		req.Host = hostHeader
	}

	resp, err := client.Do(req)
	if err != nil {
		return "", fmt.Errorf("HTTP request failed: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("failed to read response body: %w", err)
	}

	if resp.StatusCode != 200 {
		snippet := string(body)
		if len(snippet) > 200 {
			snippet = snippet[:200] + "..."
		}
		return "", fmt.Errorf("status code %d: %s", resp.StatusCode, snippet)
	}

	return string(body), nil
}

func fetchHTML(channel string) (string, error) {
	client, err := createHTTPClient()
	if err != nil {
		return "", fmt.Errorf("failed to create cookie-enabled HTTP client: %w", err)
	}

	var errors []string

	// Stage 1: TeleMirror
	mirrors := []string{
		"https://telegram.dog/s/" + channel,
		"https://tgme.org/s/" + channel,
		"https://tme.ink/s/" + channel,
	}
	var teleMirrorHTML string
	var teleMirrorErr error
	for _, mirrorURL := range mirrors {
		fmt.Fprintf(os.Stderr, "[Failover] Stage 1: Trying TeleMirror (url=%s)...\n", mirrorURL)
		teleMirrorHTML, teleMirrorErr = sendHTTPRequest(client, mirrorURL, "")
		if teleMirrorErr == nil && len(teleMirrorHTML) > 0 {
			if strings.Contains(teleMirrorHTML, "tgme_widget_message") || strings.Contains(teleMirrorHTML, "data-post=") {
				fmt.Fprintf(os.Stderr, "[Failover] Stage 1: TeleMirror succeeded using %s\n", mirrorURL)
				return teleMirrorHTML, nil
			}
		}
	}
	if teleMirrorErr == nil && len(teleMirrorHTML) > 0 {
		teleMirrorErr = fmt.Errorf("response received but does not contain posts")
	} else if teleMirrorErr == nil {
		teleMirrorErr = fmt.Errorf("no response returned")
	}
	errMsg := fmt.Sprintf("Stage 1 (TeleMirror) failed: %v", teleMirrorErr)
	fmt.Fprintf(os.Stderr, "[Failover] %s\n", errMsg)
	errors = append(errors, errMsg)

	// Stage 2: Google Fronting
	googleDomains := []string{
		"www.google.com",
		"news.google.com",
		"safebrowsing.google.com",
		"images.google.com",
		"maps.google.com",
	}
	frontDomain := googleDomains[time.Now().UnixNano()%int64(len(googleDomains))]
	googleFrontURL := fmt.Sprintf("https://%s/s/%s?_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=en&_x_tr_pto=wapp", frontDomain, channel)
	fmt.Fprintf(os.Stderr, "[Failover] Stage 2: Google Fronting (url=%s, SNI=%s, Host=t-me.translate.goog)...\n", googleFrontURL, frontDomain)

	html, err := sendHTTPRequest(client, googleFrontURL, "t-me.translate.goog")
	if err == nil && len(html) > 0 {
		if strings.Contains(html, "tgme_widget_message") || strings.Contains(html, "data-post=") {
			fmt.Fprintf(os.Stderr, "[Failover] Stage 2: Google Fronting succeeded.\n")
			return html, nil
		}
		err = fmt.Errorf("response received but does not contain posts")
	}
	if err != nil {
		errMsg := fmt.Sprintf("Stage 2 (Google Fronting) failed: %v", err)
		fmt.Fprintf(os.Stderr, "[Failover] %s\n", errMsg)
		errors = append(errors, errMsg)
	}

	// Stage 3: GoogleTranslate Direct
	translateURL := "https://t-me.translate.goog/s/" + channel + "?_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=en&_x_tr_pto=wapp"
	fmt.Fprintf(os.Stderr, "[Failover] Stage 3: GoogleTranslate Direct (url=%s)...\n", translateURL)
	html, err = sendHTTPRequest(client, translateURL, "t-me.translate.goog")
	if err == nil && len(html) > 0 {
		if strings.Contains(html, "tgme_widget_message") || strings.Contains(html, "data-post=") {
			fmt.Fprintf(os.Stderr, "[Failover] Stage 3: GoogleTranslate Direct succeeded.\n")
			return html, nil
		}
		err = fmt.Errorf("response received but does not contain posts")
	}
	if err != nil {
		errMsg := fmt.Sprintf("Stage 3 (GoogleTranslate Direct) failed: %v", err)
		fmt.Fprintf(os.Stderr, "[Failover] %s\n", errMsg)
		errors = append(errors, errMsg)
	}

	// Stage 4: Direct
	directURL := "https://t.me/s/" + channel
	fmt.Fprintf(os.Stderr, "[Failover] Stage 4: Direct (url=%s)...\n", directURL)
	html, err = sendHTTPRequest(client, directURL, "")
	if err == nil && len(html) > 0 {
		if strings.Contains(html, "tgme_widget_message") || strings.Contains(html, "data-post=") {
			fmt.Fprintf(os.Stderr, "[Failover] Stage 4: Direct succeeded.\n")
			return html, nil
		}
		err = fmt.Errorf("response received but does not contain posts")
	}
	if err != nil {
		errMsg := fmt.Sprintf("Stage 4 (Direct) failed: %v", err)
		fmt.Fprintf(os.Stderr, "[Failover] %s\n", errMsg)
		errors = append(errors, errMsg)
	}

	return "", fmt.Errorf("all failover stages failed:\n- %s", strings.Join(errors, "\n- "))
}

func parseHTMLToPosts(html string) []Post {
	var results []Post
	parts := strings.Split(html, `data-post="`)
	if len(parts) <= 1 {
		return results
	}

	for i := 1; i < len(parts); i++ {
		segment := parts[i]
		endQuoteIdx := strings.Index(segment, `"`)
		if endQuoteIdx == -1 {
			continue
		}
		dataPost := segment[:endQuoteIdx]
		slashIdx := strings.LastIndex(dataPost, "/")
		msgID := dataPost
		if slashIdx != -1 {
			msgID = dataPost[slashIdx+1:]
		}

		var postText string
		textStart := strings.Index(segment, `<div class="tgme_widget_message_text`)
		if textStart != -1 {
			tagClose := strings.Index(segment[textStart:], ">")
			if tagClose != -1 {
				innerStart := textStart + tagClose + 1
				innerHTMLEnd := findDivEnd(segment[innerStart:])
				var textHTML string
				if innerHTMLEnd != -1 {
					textHTML = segment[innerStart : innerStart+innerHTMLEnd]
				} else {
					textHTML = segment[innerStart:]
				}
				postText = cleanHTMLText(textHTML)
			}
		}

		rawMediaURL := extractMediaURL(segment)
		frontedMediaURL := frontURL(rawMediaURL)

		results = append(results, Post{
			MessageID: msgID,
			Text:      postText,
			MediaURL:  frontedMediaURL,
		})
	}

	return results
}

func main() {
	if len(os.Args) < 2 {
		fmt.Println("Usage: openfeed-fetch fetch --channel <channel> --limit <limit>")
		os.Exit(1)
	}

	subcommand := os.Args[1]
	if subcommand != "fetch" {
		fmt.Printf("Unknown subcommand: %s\n", subcommand)
		os.Exit(1)
	}

	fetchCmd := flag.NewFlagSet("fetch", flag.ExitOnError)
	channelFlag := fetchCmd.String("channel", "", "Telegram channel name")
	limitFlag := fetchCmd.Int("limit", 10, "Maximum number of posts to fetch")

	err := fetchCmd.Parse(os.Args[2:])
	if err != nil {
		fmt.Printf("Failed to parse flags: %v\n", err)
		os.Exit(1)
	}

	channel := *channelFlag
	if channel == "" {
		fmt.Println("Error: --channel is required")
		os.Exit(1)
	}

	channel = strings.TrimSpace(channel)
	channel = strings.TrimPrefix(channel, "@")

	limit := *limitFlag

	html, err := fetchHTML(channel)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error fetching channel %s:\n%v\n", channel, err)
		os.Exit(1)
	}

	posts := parseHTMLToPosts(html)

	if len(posts) == 0 {
		filePath := "/tmp/debug_response.html"
		_ = os.WriteFile(filePath, []byte(html), 0644)

		snippet := html
		if len(snippet) > 800 {
			snippet = snippet[:800] + "..."
		}
		fmt.Fprintf(os.Stderr, "\n[Debug] WARNING: Parsed 0 posts from fetched HTML!\nRaw HTML response saved to %s\nFirst 800 chars:\n%s\n\n", filePath, snippet)
	}

	for i, j := 0, len(posts)-1; i < j; i, j = i+1, j-1 {
		posts[i], posts[j] = posts[j], posts[i]
	}

	if limit > 0 && len(posts) > limit {
		posts = posts[:limit]
	}

	jsonData, err := json.Marshal(posts)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error encoding JSON: %v\n", err)
		os.Exit(1)
	}

	fmt.Println(string(jsonData))
}
