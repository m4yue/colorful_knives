package handlers

import (
	"net/http"
	"gopkg.in/redis.v5"
	"time"
	"fmt"
	"strings"
	"regexp"
	"utils"
	"strconv"
)

func HandlerDaily(w http.ResponseWriter, r *http.Request) {
	defer func() {
		if err := recover(); err != nil {
			logger.Println(err)
		}
	}()
	if r.Method == "POST" {
		r.ParseForm()
		target := r.PostForm.Get("target")
		ts := r.PostForm.Get("time")
		url := r.PostForm.Get("link")
		if len(target) == 0 || len(ts) == 0 || len(url) == 0 {
			w.WriteHeader(http.StatusBadRequest)
			return
		}
		if target == "daily" {
			timestamp, _ := strconv.Atoi(ts)
			_, err := client.ZAdd(redisKeyUrls, redis.Z{float64(timestamp), url}).Result()
			if err != nil {
				w.WriteHeader(http.StatusBadRequest)
				return
			}
			w.WriteHeader(http.StatusOK)
			return
		}

		w.WriteHeader(http.StatusBadRequest)
		return
	}
	if r.Method == "GET" {

		ret, err := client.ZRevRangeByScoreWithScores(redisKeyUrls, redis.ZRangeBy{Min: "-inf", Max: "+inf"}).Result()
		if err != nil {
			w.WriteHeader(http.StatusOK)
			return
		}
		logger.Println("zset result:", ret)
		divs := make([]string, 0)
		for _, item := range ret {
			loc, err := time.LoadLocation("Asia/Chongqing")
			if err != nil {
				w.WriteHeader(http.StatusOK)
				return
			}

			tm := time.Unix(int64(item.Score), 0).In(loc)
			tmp := fmt.Sprintf(htmlBlockTemplate, tm.Format("2006-01-02 15:04:05 -0700 MST"), item.Member)
			divs = append(divs, tmp)
		}

		w.Write([]byte(fmt.Sprintf(htmlTemplate, strings.Join(divs, ""))))
	}

}

func HandlerMarriom(w http.ResponseWriter, r *http.Request) {
	// not used
	defer func() {
		if err := recover(); err != nil {
			logger.Println(err)
		}
	}()
	if "application/x-www-form-urlencoded" == r.Header.Get("Content-Type") {
		r.ParseForm()
		content := r.PostForm.Get("text")
		logger.Println("Get slack text: ", content)
		logger.Println("Total slack content: ", r.PostForm)

		ret := regexp.MustCompile(picUrlPattern).FindAllString(content, -1)
		if ret == nil {
			w.WriteHeader(http.StatusOK)
			return
		}
		urlSet := utils.Unique(ret)
		logger.Println(fmt.Sprintf("Got %d urls: %s", len(urlSet), urlSet))
		for _, item := range urlSet {
			_, err := client.ZAdd(redisKeyUrls, redis.Z{float64(time.Now().UTC().Unix()), item}).Result()
			if err != nil {
				panic(err)
			}
		}
	}

	w.WriteHeader(http.StatusOK)
}
