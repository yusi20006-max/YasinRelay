package main

import (
	"log"
	"net/http"

	"fetcher/api"
)

func main() {

	http.Handle("/", http.FileServer(http.Dir("./fetcher/web")))

	http.HandleFunc("/api/channel/", api.Channel)

	http.HandleFunc("/api/status", api.Status)

	http.HandleFunc("/api/download", api.Download)

	http.HandleFunc("/api/image", api.Image)

	log.Println("OpenFeed started on :8080")

	log.Fatal(http.ListenAndServe(":8080", nil))

}
