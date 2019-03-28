package main

import (
	"crypto/hmac"
	"crypto/sha1"
	"strings"
	"encoding/hex"
	"net/http"
	"io/ioutil"
	"io"
	"errors"
	"utils"
	"fmt"
	"gopkg.in/redis.v5"
)

const (
	redisAddr = "localhost:6379"
	redisPassword = ""
	redisDB = 12
)

var (
	logger = utils.GetLogger("/tmp/github.log")
	client *redis.Client = redis.NewClient(&redis.Options{
		Addr:     redisAddr,
		Password: redisPassword,
		DB:       redisDB,
	})
	secret string
)

func init() {
	value, err := client.Get("github:secret").Result()
	if err != nil {
		secret = "invalid"
	} else {
		secret = value
	}
}

func signBody(secret, body []byte) []byte {
	computed := hmac.New(sha1.New, secret)
	computed.Write(body)
	return []byte(computed.Sum(nil))
}

func verifySignature(secret []byte, signature string, body []byte) bool {

	const signaturePrefix = "sha1="
	const signatureLength = 45 // len(SignaturePrefix) + len(hex(sha1))

	if len(signature) != signatureLength || !strings.HasPrefix(signature, signaturePrefix) {
		return false
	}

	actual := make([]byte, 20)
	hex.Decode(actual, []byte(signature[5:]))

	return hmac.Equal(signBody(secret, body), actual)
}

type HookContext struct {
	Signature string
	Event     string
	Id        string
	Payload   []byte
}

func ParseHook(secret []byte, req *http.Request) (*HookContext, error) {
	hc := HookContext{}

	if hc.Signature = req.Header.Get("x-hub-signature"); len(hc.Signature) == 0 {
		return nil, errors.New("No signature!")
	}

	if hc.Event = req.Header.Get("x-github-event"); len(hc.Event) == 0 {
		return nil, errors.New("No event!")
	}

	if hc.Id = req.Header.Get("x-github-delivery"); len(hc.Id) == 0 {
		return nil, errors.New("No event Id!")
	}

	body, err := ioutil.ReadAll(req.Body)

	if err != nil {
		return nil, err
	}

	if !verifySignature(secret, hc.Signature, body) {
		return nil, errors.New("Invalid signature")
	}

	hc.Payload = body

	return &hc, nil
}

func HandlerGithubWebhook(w http.ResponseWriter, r *http.Request) {
	defer func() {
		if err := recover(); err != nil {
			logger.Println(err)
			w.Write([]byte(""))
		}
	}()

	hc, err := ParseHook([]byte(secret), r)

	w.Header().Set("Content-type", "application/json")

	if err != nil {
		w.WriteHeader(http.StatusBadRequest)
		logger.Printf("Failed processing hook! ('%s')", err)
		io.WriteString(w, "{}")
		return
	}

	logger.Printf("Received %s", hc.Event)
	//only handle `push` event
	if hc.Event == "push" {
		go func() {
			logger.Println("go func go")
			//todo
		}()

	}
	w.WriteHeader(http.StatusOK)
	return
}

const (
	listenHost = "127.0.0.1"
	listenPort = 1324
)

func main() {
	http.HandleFunc("/github/webhook", HandlerGithubWebhook)

	logger.Println("Service github start at port: ", listenPort)
	http.ListenAndServe(fmt.Sprintf("%s:%d", listenHost, listenPort), nil)
}