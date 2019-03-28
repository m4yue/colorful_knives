package main

import (
	"utils"
	"fmt"
	"net/http"
	"strings"
	"github.com/bitly/go-simplejson"
	"io/ioutil"
	"golang.org/x/net/websocket"
	"time"
	"bot/handlers"
)

var (
	logger = utils.GetLogger("/tmp/bot.log")
)

func loginToSlack() {
	res, err := http.Post("https://slack.com/api/rtm.start",
		"application/x-www-form-urlencoded",
		strings.NewReader(fmt.Sprintf("token=%s", handlers.Token.BotToken)))
	if err != nil {
		//todo:retry
		logger.Println(err)
		return
	}
	if res.StatusCode != 200 {
		d, _ := ioutil.ReadAll(res.Body)
		logger.Printf("res code: %d, content: %s \n", res.StatusCode, string(d))
		return
	}

	resContent, _ := ioutil.ReadAll(res.Body)
	resJson, err := simplejson.NewJson(resContent)
	if err != nil {
		logger.Println("new json:", err)
		return
	}
	wssUrl, err := resJson.Get("url").String()
	if err != nil {
		logger.Println("Failed to get url from:", string(resContent))
		return
	}

	ws, err := websocket.Dial(wssUrl, "", "http://localhost/")
	if err != nil {
		logger.Println("web socket connect:", err)
		return
	}
	defer ws.Close()
	msg := make([]byte, int(1 << 16))//16k
	var n int
	for {
		if n, err = ws.Read(msg); err != nil {
			logger.Println("read mesg", err)
			return
		}
		logger.Println("Received: ", string(msg[:n]))
		handlers.ParseSlackMessage(msg[:n])
		time.Sleep(time.Second)
	}
}

func main() {
	logger.Println("Service bot start")
	loginToSlack()
}