package main

import (
	"log"
	"net/http"
	"os"

	"fetcher/api"
)

func main() {

	http.Handle("/", http.FileServer(http.Dir("./fetcher/web")))

	http.HandleFunc("/api/channel/", api.Channel)

	http.HandleFunc("/api/status", api.Status)

	http.HandleFunc("/api/download", api.Download)

	http.HandleFunc("/api/image", api.Image)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	addr := ":" + port

	log.Println("OpenFeed started on " + addr)

	log.Fatal(http.ListenAndServe(addr, nil))

}
