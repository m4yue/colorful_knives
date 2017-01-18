#!/usr/bin/env python
# coding: utf-8
import re
import time
import Queue
from threading import RLock
from mylogger import worker_logger
from connections import red_conn, req_ss

DEFAULT_KEYWORDS = u"所有人|all"
global_re_keywords = re.compile(r"(%s)" % DEFAULT_KEYWORDS)
request_interval = 20
keywords_lock = RLock()

SHARE_Q = Queue.LifoQueue(maxsize=100)

MAX_SLEEP_TIME = 10 * 60


def worker_send_message_to_slack():
    while True:
        # worker_logger.debug("worker slack")
        if not SHARE_Q.empty():
            data = SHARE_Q.get()
            worker_logger.debug("worker slack get: %s", data)
            try:
                url = red_conn.get("note:slack:url")
                ret = req_ss.post(url, json=data)
                if ret.status_code != 200:
                    worker_logger.error("failed to slack:%s,%s", ret.status_code, ret.text)

            except Exception as e:
                worker_logger.error("worker exception:%s", e)
                SHARE_Q.put(data)
        time.sleep(3)


def worker_set_keywords():
    global global_re_keywords
    global request_interval
    counter = 1
    while True:
        value = red_conn.get('wechat:filter:keywords')
        interval = red_conn.get('wechat:request:interval')
        keywords_lock.acquire()
        if not value:
            worker_logger.info("no value found in redis, using default setting.")
            global_re_keywords = re.compile(r"(%s)" % DEFAULT_KEYWORDS)
        else:
            # value format: "xxx|xxx|xxx"
            try:
                global_re_keywords = re.compile(r"(%s)" % value.decode('utf-8'))
            except Exception as e:
                worker_logger.exception("get keywords failed.<%s>", e)
                global_re_keywords = re.compile(r"(%s)" % DEFAULT_KEYWORDS)
        # worker_logger.info("interval: %s", interval)
        if interval:
            request_interval = int(interval)
        keywords_lock.release()
        # worker_logger.debug('keywords:%s', global_re_keywords.pattern)

        time.sleep(counter)

        if counter < MAX_SLEEP_TIME:
            counter += 2


def get_re_object():
    return global_re_keywords


def get_request_interval():
    return request_interval
