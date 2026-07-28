package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"regexp"
	"strings"
	"time"

	"fetcher/telemirror"
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

func extractMessageID(pID string) string {
	parts := strings.Split(pID, "/")
	if len(parts) > 1 {
		return parts[len(parts)-1]
	}
	return pID
}

func mapPost(p telemirror.Post) Post {
	msgID := extractMessageID(p.ID)
	text := cleanHTMLText(p.Text)

	var mediaURL string
	if len(p.Media) > 0 {
		m := p.Media[0]
		if m.Thumb != "" {
			mediaURL = m.Thumb
		} else if m.URL != "" {
			mediaURL = m.URL
		}
	}
	mediaURL = frontURL(mediaURL)

	return Post{
		MessageID: msgID,
		Text:      text,
		MediaURL:  mediaURL,
	}
}

func main() {
	if len(os.Args) < 2 {
		fmt.Println("Usage: openfeed-fetch <subcommand> [flags]")
		fmt.Println("Subcommands:")
		fmt.Println("  fetch     Fetch posts from a Telegram channel")
		fmt.Println("  download  Download media from a URL using telemirror")
		os.Exit(1)
	}

	subcommand := os.Args[1]
	if subcommand != "fetch" && subcommand != "download" {
		fmt.Printf("Unknown subcommand: %s\n", subcommand)
		os.Exit(1)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 45*time.Second)
	defer cancel()

	client := telemirror.NewClient()

	if subcommand == "fetch" {
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

		htmlBody, err := client.FetchHTML(ctx, channel)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error fetching channel %s: %v\n", channel, err)
			os.Exit(1)
		}

		_, parsedPosts, err := telemirror.ParseHTML(htmlBody)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error parsing channel %s: %v\n", channel, err)
			os.Exit(1)
		}

		var posts []Post
		for _, p := range parsedPosts {
			posts = append(posts, mapPost(p))
		}

		// Reverse to put the newest posts first
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
	} else if subcommand == "download" {
		downloadCmd := flag.NewFlagSet("download", flag.ExitOnError)
		urlFlag := downloadCmd.String("url", "", "URL of the media to download")

		err := downloadCmd.Parse(os.Args[2:])
		if err != nil {
			fmt.Printf("Failed to parse flags: %v\n", err)
			os.Exit(1)
		}

		urlStr := *urlFlag
		if urlStr == "" {
			fmt.Println("Error: --url is required")
			os.Exit(1)
		}

		bytes, _, err := client.FetchDownload(ctx, urlStr)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error downloading URL %s: %v\n", urlStr, err)
			os.Exit(1)
		}

		_, err = os.Stdout.Write(bytes)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error writing download to stdout: %v\n", err)
			os.Exit(1)
		}
	}
}
