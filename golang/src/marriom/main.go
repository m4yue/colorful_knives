package main

import (
	"net/http"
	"fmt"
	"marriom/handlers"
	"utils"
)

const (
	listenHost = "127.0.0.1"
	listenPort = 1323
)

func main() {
	http.HandleFunc("/daily", handlers.HandlerDaily)
	http.HandleFunc("/messages/marriom", handlers.HandlerMarriom)
	//http.HandleFunc("/oauth/slack", handlers.HandlerSlackOAuth)
	//http.HandleFunc("/events/slack", handlers.HandlerSlackEvents)
	http.HandleFunc("/commands/slack", handlers.HandlerSlackCommands)

	utils.GetLogger("/tmp/marriom.log").Println("Service start at port: ", listenPort)
	http.ListenAndServe(fmt.Sprintf("%s:%d", listenHost, listenPort), nil)
}