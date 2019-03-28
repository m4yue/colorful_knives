package handlers

import (
	"net/http"
	"io"
	"io/ioutil"
	"github.com/bitly/go-simplejson"
	"strings"
	"encoding/base64"
	"bot/handlers"
	"fmt"
	"regexp"
	"time"
	"strconv"
)

func readBody(r *http.Request) []byte {
	if r.Body == nil {
		return []byte("")
	}

	b, e := ioutil.ReadAll(io.LimitReader(r.Body, int64(1 << 12))) //4kB is enough for my small host.

	if e != nil {
		return []byte("")
	}

	return b
}

func HandlerSlackEvents(w http.ResponseWriter, r *http.Request) {
	defer func() {
		if err := recover(); err != nil {
			logger.Println(err)
		}
	}()

	if r.Method != "POST" {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	body := readBody(r)
	logger.Println("Body: ", string(body))

	jsonEvent, err := simplejson.NewJson(body)

	if err != nil {
		logger.Println(err)
		w.WriteHeader(http.StatusOK)
		return
	}

	switch eventType, _ := jsonEvent.Get("type").String(); eventType {
	case "url_verification":
		slackChallenge, _ := jsonEvent.Get("challenge").Bytes()
		w.Header().Set("Content-Type", "application/x-www-form-urlencoded")
		w.Write(slackChallenge)
	case "event_callback":
		eventDetail, err := jsonEvent.Get("event").Map()
		if err != nil {
			logger.Println(err)
			w.WriteHeader(http.StatusOK)
			return
		}

		switch value, _ := eventDetail["type"].(string); value{
		case "file_created":
			fileObject, err := jsonEvent.Get("event").Get("file").Map()
			logger.Println("File object: ", fileObject)
			if err != nil {
				logger.Println(err)
				w.WriteHeader(http.StatusOK)
				return

			}
			//only handle image now.
			if fileType, _ := fileObject["mimetype"].(string); !strings.Contains(fileType, "image") {
				w.WriteHeader(http.StatusOK)
				return
			}
		default:
			logger.Println("Unhandled event:", eventDetail)
		}

	default:
		logger.Println("Unhandled event type: ", eventType)
	}
	return
}

func GetChannelMessages(channel string) []interface{} {
	res, err := http.Post("https://slack.com/api/channels.history",
		"application/x-www-form-urlencoded",
		strings.NewReader(fmt.Sprintf("token=%s&channel=%s", handlers.Token.BotToken, channel)))
	if err != nil {
		logger.Println("Failed to connect to slack chat history:", err)
		return nil
	}
	ret, _ := ioutil.ReadAll(res.Body)
	if res.StatusCode == 200 {
		hisJson, err := simplejson.NewJson(ret)
		if err != nil {
			logger.Println("Failed history json:", err)
			return nil
		}
		messages, err := hisJson.Get("messages").Array()
		if err != nil {
			logger.Println("Failed to get messages from history json", err)
			return nil
		}
		return messages
	} else {
		logger.Println("Failed to get history", res.StatusCode, ret)
		return nil
	}
}

func DeleteMessage(channel, ts string) {
	res, err := http.Post("https://slack.com/api/chat.delete",
		"application/x-www-form-urlencoded",
		strings.NewReader(fmt.Sprintf("token=%s&channel=%s&ts=%s", handlers.Token.BotToken, channel, ts)))
	if err != nil {
		logger.Println("Failed to connect to slack chat delte:", err)
		return
	}
	if res.StatusCode == 200 {
		logger.Println("Successfully delete messages")
	} else {
		ret, _ := ioutil.ReadAll(res.Body)
		logger.Println("Failed to delete messages", res.StatusCode, ret)
	}
}

func DeleteMessages(channel string, tsBefore int64) {
	messages := GetChannelMessages(channel)
	if messages == nil {
		return
	}

	for _, value := range (messages) {
		if msgBody, ok := value.(map[string]interface{}); ok {
			msgTime := msgBody["ts"]
			if stringMsgTime, ok := msgTime.(string); ok {
				floatMsgTime, _ := strconv.ParseFloat(stringMsgTime, 64)
				if int64(floatMsgTime) < tsBefore {
					go DeleteMessage(channel, stringMsgTime)
				}
			}
		}
	}
	return
}

func HandlerSlackCommands(w http.ResponseWriter, r *http.Request) {
	defer func() {
		if err := recover(); err != nil {
			logger.Println(err)
			w.Write([]byte(""))
		}
	}()
	if "application/x-www-form-urlencoded" == r.Header.Get("Content-Type") {
		r.ParseForm()

		switch r.PostForm.Get("command")  {
		case "/b64e":
			text := r.PostForm.Get("text")
			w.Write([]byte(base64.StdEncoding.EncodeToString([]byte(text))))
		case "/b64d":
			ret, _ := base64.StdEncoding.DecodeString(r.PostForm.Get("text"))
			w.Write(ret)
		case "/deletemsgs":
			channelId := r.PostForm.Get("channel_id")
			text := r.PostForm.Get("text")
			logger.Println(text)
			// text: -25 means 25 hours before now.
			// e.g. we are going to delete messages that exists before 25 hours ago.
			timeRange := regexp.MustCompile(hoursPattern).FindAllStringSubmatch(text, 1)
			if len(timeRange) == 0 {
				logger.Println("Unable to find timerange from ", text)
				return
			}
			timeInt, _ := strconv.Atoi(timeRange[0][1])

			go DeleteMessages(channelId, time.Now().Unix() - int64(timeInt * 3600))

			w.Write([]byte("Deleted messages."))

		default:
			logger.Println("Total slack command: ", r.PostForm)
		}
	}

}