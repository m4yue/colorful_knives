package handlers

import (
	"gopkg.in/redis.v5"
	"utils"
	"log"
)

const (
	redisAddr = "localhost:6379"
	redisPassword = ""
	redisDB = 12
	//todo: move configuration to redis.
	picUrlPattern = `http.*?.(jpg|png|gif)`
	hoursPattern = `-([0-9]{1,4})`

	redisKeyUrls = "marriom:daily:urls"
	htmlTemplate = `<!DOCTYPE html><html lang="zh-cn"><head><meta charset="utf-8">
	<meta http-equiv="X-UA-Compatible" content="IE=edge">
    	<meta name="viewport" content="width=device-width, initial-scale=1">
    	<title>Marriom Daily Pictures</title>
    	<link rel="stylesheet" href="https://cdn.bootcss.com/bootstrap/3.3.7/css/bootstrap.min.css">
  	</head><body><div class="container">%s</div>
    	<script src="https://cdn.bootcss.com/jquery/3.1.1/jquery.min.js"></script>
    	<script src="https://cdn.bootcss.com/bootstrap/3.3.7/js/bootstrap.min.js"></script>
  	</body></html>`
	htmlBlockTemplate = `<div class="row">
	<h3>%s</h3>
	<img src="%s" class="img-responsive"/>
	<hr></div>`
)

var (
	logger *log.Logger = utils.GetLogger("/tmp/marriom.log")
	client *redis.Client = redis.NewClient(&redis.Options{
		Addr:     redisAddr,
		Password: redisPassword,
		DB:       redisDB,
	})
)
