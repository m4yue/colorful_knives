package handlers

import (
	"regexp"
	"net/http"
	"utils"
	"fmt"
	"github.com/bitly/go-simplejson"
	"strings"
	"io/ioutil"
)

func DeleteFile(fileId string) {
	res, err := http.Post("https://slack.com/api/files.delete",
		"application/x-www-form-urlencoded",
		strings.NewReader(fmt.Sprintf("token=%s&file=%s", Token.BotToken, fileId)))
	if err != nil {
		logger.Println("Failed to connect slack:", err)
		return
	}
	if res.StatusCode == 200 {
		logger.Println("Successfully delete file:", fileId)
		return
	} else {
		ret, _ := ioutil.ReadAll(res.Body)
		logger.Println("Failed to delete file:", fileId, res.StatusCode, ret)
		return
	}
}

func HandleText(text string) {
	ret := regexp.MustCompile(picUrlPattern).FindAllString(text, -1)
	if ret == nil {
		return
	}
	urlSet := utils.Unique(ret)
	logger.Println(fmt.Sprintf("Got %d urls: %s", len(urlSet), urlSet))
	for _, item := range urlSet {
		if !strings.Contains(item, "slack.com") {
			SaveImageInRedis(item)
		}
	}
}

func HandleImage(file map[string]interface{}) {
	fileId, ok := file["id"].(string);
	if !ok {
		logger.Println("Invalid image file ID")
	}

	privateUrl, ok := file["url_private"].(string);
	if !ok {
		logger.Println("Invalid image file url_private")
	}
	//download
	req, err := http.NewRequest("GET", privateUrl, nil)
	if err != nil {
		logger.Println("Failed to new request:", err)
	}
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", Token.BotToken))
	res, err := http.DefaultClient.Do(req)
	if err != nil {
		logger.Println("Failed to get img:", err)
		return
	}
	if res.StatusCode != 200 {
		logger.Println("Failed to get img code:", res.StatusCode)
		return
	}
	if !strings.Contains(res.Header.Get("Content-Type"), "image") {
		logger.Println("Get invalid file type: ", res.Header.Get("Content-Type"))
		return
	}

	imgBytes := RemoveEXIF(res.Body)
	if len(imgBytes) == 0 {
		return
	}
	ret := UploadPicToQiniu(fileId, imgBytes)
	logger.Println("Uploaded: ", ret)
	success := SaveImageInRedis(DefaultBucketUrl + ret + ImgHandlerName)
	if success {
		DeleteFile(fileId)
	}

}

func HandleFile(file map[string]interface{}) {
	//only handle image now.
	fileType, _ := file["mimetype"].(string);

	if strings.Contains(fileType, "image") {
		HandleImage(file)
	}
}

func ParseSlackMessage(msg []byte) {
	wsJson, err := simplejson.NewJson(msg)
	if err != nil {
		logger.Println("websocket json:", err)
		return
	}
	wsType, err := wsJson.Get("type").String()
	if err != nil {
		logger.Println("Failed to get message type from:", wsJson)
		return
	}
	switch wsType {
	case "message":
		wsSubType, _ := wsJson.Get("subtype").String()
		switch wsSubType {
		case "file_share":
			fileInfo, err := wsJson.Get("file").Map()
			if err != nil {
				logger.Println("file_share json error: ", err)
			}
			HandleFile(fileInfo)
		default:
		}
		wsText, _ := wsJson.Get("text").String()
		if wsText != "" {
			HandleText(wsText)
			return
		}
	case "file_created":
		fileInfo, err := wsJson.Get("file").Map()
		if err != nil {
			logger.Println("file_created json error: ", err)
		}
		HandleFile(fileInfo)
	default:


	}
}