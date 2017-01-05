#!/usr/bin/env python
# coding: utf-8
import re
import time
import Queue
from threading import RLock
from mylogger import logger
from connections import red_conn, req_ss

DEFAULT_KEYWORDS = u"所有人|all"
global_re_keywords = re.compile(r"(%s)" % DEFAULT_KEYWORDS)
keywords_lock = RLock()

SHARE_Q = Queue.LifoQueue(maxsize=100)


def worker_send_message_to_slack():
    while True:
        if not SHARE_Q.empty():
            data = SHARE_Q.get()
            try:
                url = red_conn.get("note:slack:url")
                ret = req_ss.post(url, json=data)
                if ret.status_code != 200:
                    logger.error("failed to slack:%s,%s", ret.status_code, ret.text)

            except Exception as e:
                logger.error("worker exception:%s", e)
                SHARE_Q.put(data)
        time.sleep(1)


def worker_set_keywords():
    global global_re_keywords
    while True:
        value = red_conn.get('wechat:filter:keywords')
        keywords_lock.acquire()
        if not value:
            logger.info("no value found in redis, using default setting.")
            global_re_keywords = re.compile(r"(%s)" % DEFAULT_KEYWORDS)
        else:
            # value format: "xxx|xxx|xxx"
            try:
                global_re_keywords = re.compile(r"(%s)" % value.decode('utf-8'))
            except Exception as e:
                logger.exception("get keywords failed.<%s>", e)
                global_re_keywords = re.compile(r"(%s)" % DEFAULT_KEYWORDS)

        keywords_lock.release()
        time.sleep(5)


def get_re_object():
    return global_re_keywords
