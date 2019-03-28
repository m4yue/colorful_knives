package handlers

import (
	"fmt"
	"time"
	"encoding/base64"
	"crypto/hmac"
	"crypto/sha1"
	"github.com/bitly/go-simplejson"
	"github.com/parnurzeal/gorequest"
	"encoding/json"
)

var request *gorequest.SuperAgent = gorequest.New()

const (
	BucketName = "marriom"
	GatewayHost = "https://uc.qbox.me"
	DefaultBucketUrl = "http://ok44hlsr3.bkt.clouddn.com/"
)

type QiniuRespose struct {
	Hash string `json:"hash"`
	Key  string `json:"key"`
}

func GetUpHosts() string {
	_, body, errs := request.Get(GatewayHost + fmt.Sprintf("/v1/query?ak=%s&bucket=%s", Token.QiniuAK, BucketName)).End()
	if errs != nil {
		logger.Println("Failed to gateway host:", errs)
		return ""
	}
	qJson, err := simplejson.NewJson([]byte(body))
	if err != nil {
		logger.Println("Failed to get json:", err)
		return ""
	}
	httpsUrls, err := qJson.Get("https").Map()
	if err != nil {
		logger.Println("Failed to convert json field:", err)
		return ""
	}
	_, ok := httpsUrls["up"].([]interface{})
	//logger.Println(httpsUrls)
	//logger.Println(httpsUrls["up"])
	//logger.Println(reflect.TypeOf(httpsUrls["up"]), reflect.ValueOf(httpsUrls["up"]))
	if !ok {
		logger.Println("Failed to convert upload url:", ok)
		return ""
	}
	return "https://up-z2.qbox.me"
	//return "http://localhost:13111"
}

func BuildSimplePolicy(name string) string {
	simplePolicy := fmt.Sprintf(
		`{"scope":"%s","deadline":%d}`,
		name,
		time.Now().Unix() + int64(600))//10 minutes
	encodedPolicy := base64.URLEncoding.EncodeToString([]byte(simplePolicy))
	mac := hmac.New(sha1.New, []byte(Token.QiniuSK))
	mac.Write([]byte(encodedPolicy))
	hashedPolicy := mac.Sum(nil)
	encodedSign := base64.URLEncoding.EncodeToString(hashedPolicy)
	uploadToken := Token.QiniuAK + ":" + encodedSign + ":" + encodedPolicy
	return uploadToken
}

func UploadPicToQiniu(name string, fileContent []byte) string {
	reqBody := request.Post("https://up-z2.qbox.me").Type("multipart").
	Set("User-Agent", "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36").
	Send(fmt.Sprintf(`{"token":"%s"}`, BuildSimplePolicy(BucketName)))

	reqBody.FileData = append(reqBody.FileData, gorequest.File{
		Filename:  name,
		Fieldname: "file",
		Data:      fileContent,
	})

	resp, body, err := reqBody.End()
	if err != nil {
		logger.Println("Failed to upload file content:", err)
		return ""
	}
	if resp.StatusCode != 200 {
		logger.Println("Failed to upload to qiniu: ",fmt.Sprintf("%d, %s", resp.StatusCode, body))
		return ""
	} else {
		respJson := new(QiniuRespose)
		json.Unmarshal([]byte(body), respJson)
		return respJson.Key
	}
}
