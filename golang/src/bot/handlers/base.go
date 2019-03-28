package handlers

import (
	"gopkg.in/redis.v5"
	"utils"
	"log"
	"time"
	"image"
	"image/jpeg"
	"io"
	"qiniupkg.com/x/bytes.v7"
)

const (
	redisAddr = "localhost:6379"
	redisPassword = ""
	redisDB = 12
	//todo: move configuration to redis.
	picUrlPattern = `http.*?.(jpg|png|gif)`
	redisKeyUrls = "marriom:daily:urls"
	ImgHandlerName = "-marriom"
)

type Tokens struct {
	BotToken string
	QiniuSK  string //SecretKey
	QiniuAK  string //AccessKey
}

var (
	logger *log.Logger = utils.GetLogger("/tmp/bot.log")
	client *redis.Client = redis.NewClient(&redis.Options{
		Addr:     redisAddr,
		Password: redisPassword,
		DB:       redisDB,
	})
	Token Tokens
	buff []byte
)

func GetToken(key string) string {
	value, err := client.Get(key).Result()

	if err != nil {
		panic(err)
	} else {
		logger.Printf("Get %s:%s\n", key, value)
		return value
	}

}

func init() {
	Token = Tokens{}
	Token.BotToken = GetToken("slack:bot:token")
	Token.QiniuAK = GetToken("qiniu:token:access")
	Token.QiniuSK = GetToken("qiniu:token:secret")
	buff = make([]byte, 1 << 22) //4MB
}

func SaveImageInRedis(picUrl string) bool {
	_, err := client.ZAdd(redisKeyUrls, redis.Z{float64(time.Now().UTC().Unix()), picUrl}).Result()
	if err != nil {
		logger.Println("Failed to save imgUrl: ", err)
		return false
	}
	logger.Println("Saved imgUrl: ", picUrl)
	return true
}

func RemoveEXIF(target io.ReadCloser) []byte {
	img, _, err := image.Decode(target)
	if err != nil {
		logger.Println("Failed to decode image ", err)
		return []byte("")
	}

	outFile := bytes.NewWriter(buff)

	if err := jpeg.Encode(outFile, img, nil); err != nil {
		logger.Println("Failed to encode jpeg ", err)
		return []byte("")
	}
	return outFile.Bytes()
}