package utils

import (
	"os"
	"log"
)

//only support one logger in one application.
var myLogger *log.Logger = nil

func GetLogger(fileName string) *log.Logger {
	if myLogger == nil {
		fd, _ := os.OpenFile(fileName, os.O_CREATE | os.O_RDWR | os.O_APPEND, os.ModePerm)
		myLogger = log.New(fd, "", 1)
	}

	return myLogger
}