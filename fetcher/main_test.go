package main

import (
	"reflect"
	"testing"

	"fetcher/telemirror"
)

func parseHTMLToPosts(html string) []Post {
	_, parsedPosts, err := telemirror.ParseHTML(html)
	if err != nil {
		return nil
	}
	var posts []Post
	for _, p := range parsedPosts {
		posts = append(posts, mapPost(p))
	}
	return posts
}

func TestFrontURL(t *testing.T) {
	tests := []struct {
		input    string
		expected string
	}{
		{"https://cdn4.telesco.pe/file/abc", "https://cdn4-telesco-pe.translate.goog/file/abc"},
		{"http://cdn1.telesco.pe/file/xyz", "http://cdn1-telesco-pe.translate.goog/file/xyz"},
		{"https://cdn.telesco.pe/file/123", "https://cdn-telesco-pe.translate.goog/file/123"},
		{"https://telesco.pe/file/abc", "https://telesco-pe.translate.goog/file/abc"},
		{"https://google.com", "https://google.com"},
		{"", ""},
	}

	for _, tc := range tests {
		got := frontURL(tc.input)
		if got != tc.expected {
			t.Errorf("frontURL(%q) = %q; expected %q", tc.input, got, tc.expected)
		}
	}
}

func TestCleanHTMLText(t *testing.T) {
	input := "Hello <br> World! <p>This is <b>bold</b>.</p> &amp; &lt; &gt; &quot; &#39;"
	expected := "Hello \n World! This is bold. & < > \" '"
	got := cleanHTMLText(input)
	if got != expected {
		t.Errorf("cleanHTMLText(%q) = %q; expected %q", input, got, expected)
	}
}

func TestParseHTMLToPosts(t *testing.T) {
	html := `
	<div class="tgme_widget_message_wrap">
		<div class="tgme_widget_message js-widget_message" data-post="mychannel/101">
			<div class="tgme_widget_message_user_photo">
				<img src="https://cdn4.telesco.pe/file/avatar.jpg">
			</div>
			<div class="tgme_widget_message_photo_wrap" style="background-image:url('https://cdn4.telesco.pe/file/photo1.jpg')"></div>
			<div class="tgme_widget_message_text js-message_text">Hello &amp; Welcome!</div>
		</div>
	</div>
	<div class="tgme_widget_message_wrap">
		<div class="tgme_widget_message js-widget_message" data-post="mychannel/102">
			<div class="tgme_widget_message_user_photo">
				<img src="https://cdn4.telesco.pe/file/avatar.jpg">
			</div>
			<div class="tgme_widget_message_text js-message_text">No photo post</div>
		</div>
	</div>
	`

	expected := []Post{
		{
			MessageID: "101",
			Text:      "Hello & Welcome!",
			MediaURL:  "https://cdn4-telesco-pe.translate.goog/file/photo1.jpg",
		},
		{
			MessageID: "102",
			Text:      "No photo post",
			MediaURL:  "",
		},
	}

	got := parseHTMLToPosts(html)
	if !reflect.DeepEqual(got, expected) {
		t.Errorf("parseHTMLToPosts() = %+v; expected %+v", got, expected)
	}
}
