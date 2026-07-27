package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
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

func sendHTTPRequest(urlStr string, hostHeader string) (string, error) {
	client := &http.Client{
		Timeout: 15 * time.Second,
	}
	req, err := http.NewRequest("GET", urlStr, nil)
	if err != nil {
		return "", err
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
	if hostHeader != "" {
		req.Host = hostHeader
		req.Header.Set("Host", hostHeader)
	}
	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return "", fmt.Errorf("status code %d", resp.StatusCode)
	}
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}
	return string(body), nil
}

func fetchHTML(channel string) (string, error) {
	// Failover chain: TeleMirror -> Google -> GoogleTranslate -> Direct

	// 1. TeleMirror
	html, err := sendHTTPRequest("https://tme.ink/s/"+channel, "")
	if err == nil && len(html) > 0 {
		return html, nil
	}

	// 2. Google (Domain Fronting)
	html, err = sendHTTPRequest("https://www.google.com/s/"+channel+"?_x_tr_sl=el&_x_tr_tl=en&_x_tr_hl=en&_x_tr_pto=wapp", "t-me.translate.goog")
	if err == nil && len(html) > 0 {
		return html, nil
	}

	// 3. GoogleTranslate (Direct to t-me.translate.goog)
	html, err = sendHTTPRequest("https://t-me.translate.goog/s/"+channel+"?_x_tr_sl=el&_x_tr_tl=en&_x_tr_hl=en&_x_tr_pto=wapp", "t-me.translate.goog")
	if err == nil && len(html) > 0 {
		return html, nil
	}

	// 4. Direct
	html, err = sendHTTPRequest("https://t.me/s/"+channel, "")
	if err == nil && len(html) > 0 {
		return html, nil
	}

	return "", fmt.Errorf("failed to fetch channel content from all failover sources")
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
		fmt.Fprintf(os.Stderr, "Error fetching channel %s: %v\n", channel, err)
		os.Exit(1)
	}

	posts := parseHTMLToPosts(html)

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
