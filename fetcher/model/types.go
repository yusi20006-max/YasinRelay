package model

type Channel struct {
	Title       string `json:"title"`
	Username    string `json:"username"`
	Avatar      string `json:"avatar"`
	Description string `json:"description"`
	Subscribers string `json:"subscribers"`
	Posts       []Post `json:"posts"`
}

type Media struct {
	Type     string  `json:"type"`
	URL      string  `json:"url,omitempty"`
	Ratio    float64 `json:"ratio,omitempty"`
	Download string  `json:"download,omitempty"`
	Duration string  `json:"duration,omitempty"`
	Title    string  `json:"title,omitempty"`
	Subtitle string  `json:"subtitle,omitempty"`
}

type Post struct {
	ID     string  `json:"id"`
	Author string  `json:"author,omitempty"`
	Date   string  `json:"date"`
	Text   string  `json:"text"`
	Media  []Media `json:"media"`
	Views  string  `json:"views"`
}
