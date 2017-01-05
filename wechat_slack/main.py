#!/usr/bin/env python
# coding: utf-8
import qrcode
import urllib
import urllib2
import cookielib
import requests
import xml.dom.minidom
import json
import time
import re
import sys
import random
import multiprocessing
from threading import Thread, RLock
import logging.config
import httplib
from redis import StrictRedis
import Queue

red_conn = StrictRedis(db=15)

DEFAULT_KEYWORDS = u"所有人|all"

global_re_keywords = re.compile(r"(%s)" % DEFAULT_KEYWORDS)

keywords_lock = RLock()

req_ss = requests.session()

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


def set_keywords():
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


def catchKeyboardInterrupt(fn):
    def wrapper(*args):
        try:
            return fn(*args)
        except KeyboardInterrupt:
            print '\n[*] 强制退出程序'
            logger.debug('[*] 强制退出程序')

    return wrapper


class WebWeixin(object):
    def __str__(self):
        description = \
            "=========================\n" + \
            "[#] Web Weixin\n" + \
            "[#] Debug Mode: " + str(self.DEBUG) + "\n" + \
            "[#] Uuid: " + self.uuid + "\n" + \
            "[#] Uin: " + str(self.uin) + "\n" + \
            "[#] Sid: " + self.sid + "\n" + \
            "[#] Skey: " + self.skey + "\n" + \
            "[#] DeviceId: " + self.deviceId + "\n" + \
            "[#] PassTicket: " + self.pass_ticket + "\n" + \
            "========================="
        return description

    def __init__(self):
        self.DEBUG = False
        self.uuid = ''
        self.base_uri = ''
        self.redirect_uri = ''
        self.uin = ''
        self.sid = ''
        self.skey = ''
        self.pass_ticket = ''
        self.deviceId = 'e' + repr(random.random())[2:17]
        self.BaseRequest = {}
        self.synckey = ''
        self.SyncKey = []
        self.User = []
        self.friends = {}  # 好友
        self.groups = {}  # 群
        self.group_friends = {}  # 群友
        self.syncHost = ''
        self.user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.109 Safari/537.36'

        self.appid = 'wx782c26e4c19acffb'
        self.lang = 'zh_CN'
        self.last_check = time.time()
        self.memberCount = 0

        self.TimeOut = 20  # 同步最短时间间隔（单位：秒）
        self.media_count = -1

        self.cookie = cookielib.CookieJar()
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookie))
        opener.addheaders = [('User-agent', self.user_agent)]
        urllib2.install_opener(opener)

    def get_wechat_uuid(self):
        url = 'https://login.weixin.qq.com/jslogin'
        data = self._post(url, {'appid': self.appid,
                                'fun': 'new',
                                'lang': self.lang,
                                '_': int(time.time()),
                                }, False)
        if data == '':
            return False
        regx = r'window.QRLogin.code = (\d+); window.QRLogin.uuid = "(\S+?)"'
        pm = re.search(regx, data)
        if pm:
            code = pm.group(1)
            self.uuid = pm.group(2)
            return code == '200'
        return False

    def gen_qrcode(self):
        url = 'https://login.weixin.qq.com/l/' + self.uuid
        logger.debug("qrcode url:%s", url)
        qr = qrcode.QRCode()
        qr.border = 1
        qr.add_data(url)
        qr.make()
        # img = qr.make_image()
        # img.save("qrcode.png")
        # mat = qr.get_matrix()
        # self._printQR(mat)  # qr.print_tty() or qr.print_ascii()
        qr.print_ascii(invert=True)

    def wait_for_login(self, tip=1):
        time.sleep(tip)
        url = 'https://login.weixin.qq.com/cgi-bin/mmwebwx-bin/login?tip=%s&uuid=%s&_=%s' % (
            tip, self.uuid, int(time.time()))
        data = self._get(url)
        if data == '':
            return False
        pm = re.search(r'window.code=(\d+);', data)
        code = pm.group(1)

        if code == '201':
            return True
        elif code == '200':
            pm = re.search(r'window.redirect_uri="(\S+?)";', data)
            r_uri = pm.group(1) + '&fun=new'
            self.redirect_uri = r_uri
            self.base_uri = r_uri[:r_uri.rfind('/')]
            return True
        elif code == '408':
            logger.error('[登陆超时]')
        else:
            logger.error('[登陆异常]')
        return False

    def login(self):
        data = self._get(self.redirect_uri)
        if data == '':
            return False
        doc = xml.dom.minidom.parseString(data)
        root = doc.documentElement

        for node in root.childNodes:
            if node.nodeName == 'skey':
                self.skey = node.childNodes[0].data
            elif node.nodeName == 'wxsid':
                self.sid = node.childNodes[0].data
            elif node.nodeName == 'wxuin':
                self.uin = node.childNodes[0].data
            elif node.nodeName == 'pass_ticket':
                self.pass_ticket = node.childNodes[0].data

        if '' in (self.skey, self.sid, self.uin, self.pass_ticket):
            return False

        self.BaseRequest = {'Uin': int(self.uin),
                            'Sid': self.sid,
                            'Skey': self.skey,
                            'DeviceID': self.deviceId,
                            }
        return True

    def init_web_weixin(self):
        url = self.base_uri + '/webwxinit?pass_ticket=%s&skey=%s&r=%s' % (
            self.pass_ticket, self.skey, int(time.time()))
        params = {
            'BaseRequest': self.BaseRequest
        }
        dic = self._post(url, params)
        if dic == '':
            return False
        self.SyncKey = dic['SyncKey']
        self.User = dic['User']
        # synckey for synccheck
        self.synckey = '|'.join(
            [str(keyVal['Key']) + '_' + str(keyVal['Val']) for keyVal in self.SyncKey['List']])

        return dic['BaseResponse']['Ret'] == 0

    def handle_status_notification(self):
        url = self.base_uri + '/webwxstatusnotify?lang=zh_CN&pass_ticket=%s' % self.pass_ticket

        dic = self._post(url, {'BaseRequest': self.BaseRequest,
                               "Code": 3,
                               "FromUserName": self.User['UserName'],
                               "ToUserName": self.User['UserName'],
                               "ClientMsgId": int(time.time())
                               })
        if dic == '':
            return False

        return dic['BaseResponse']['Ret'] == 0

    def get_contacts(self):
        url = self.base_uri + '/webwxgetcontact?pass_ticket=%s&skey=%s&r=%s' % (
            self.pass_ticket, self.skey, int(time.time()))
        dic = self._post(url, {})

        if dic == '':
            return False
        for item in dic['MemberList']:
            if int(item['VerifyFlag']) == 0:  # normal friends
                self.friends[item['UserName']] = {"nick": item.get("NickName", "unknown"),
                                                  "remark": item.get("RemarkName", "unknown")
                                                  }
        return True

    def update_group_info(self, group_id):
        url = self.base_uri + '/webwxbatchgetcontact?type=ex&r=%s&pass_ticket=%s' % (int(time.time()), self.pass_ticket)

        dic = self._post(url, {'BaseRequest': self.BaseRequest,
                               "Count": 1,
                               "List": [{'UserName': group_id, 'EncryChatRoomId': ''}]
                               })
        if dic == '':
            return False

        # logger.debug("============groups: %s", dic)
        group_info = dic['ContactList'][0]
        self.groups[group_id] = {'nick': group_info['NickName'],
                                 'remark': group_info['RemarkName']
                                 }
        self.group_friends.update({b['UserName']: {'nick': b['NickName'], 'remark': b['DisplayName']}
                                   for b in group_info['MemberList']})
        # logger.debug("============groups: %s", self.groups[group_id])

    def check_wexin_hosts(self):
        SyncHost = ['webpush.weixin.qq.com',
                    # 'webpush2.weixin.qq.com',
                    'webpush.wechat.com',
                    'webpush1.wechat.com',
                    'webpush2.wechat.com',
                    'webpush.wx.qq.com',
                    'webpush2.wx.qq.com'
                    # 'webpush.wechatapp.com'
                    ]
        for host in SyncHost:
            self.syncHost = host
            [retcode, selector] = self.synccheck()
            if retcode == '0':
                return True
        return False

    def synccheck(self):
        url = 'https://' + self.syncHost + '/cgi-bin/mmwebwx-bin/synccheck?' + urllib.urlencode({'r': int(time.time()),
                                                                                                 'sid': self.sid,
                                                                                                 'uin': self.uin,
                                                                                                 'skey': self.skey,
                                                                                                 'deviceid': self.deviceId,
                                                                                                 'synckey': self.synckey,
                                                                                                 '_': int(time.time()),
                                                                                                 })
        data = self._get(url)
        if data == '':
            return [-1, -1]
        pm = re.search(r"window.synccheck={retcode:\"(\d+)\",selector:\"(\d+)\"}", data)
        if not pm:
            logger.error("invalid sync check response:%s", data)
        return pm.groups()

    def retrieve_messages(self):
        url = self.base_uri + '/webwxsync?sid=%s&skey=%s&pass_ticket=%s' % (self.sid, self.skey, self.pass_ticket)

        dic = self._post(url, {'BaseRequest': self.BaseRequest,
                               'SyncKey': self.SyncKey,
                               'rr': ~int(time.time())
                               })
        if dic == '':
            return None

        if dic['BaseResponse']['Ret'] == 0:
            self.SyncKey = dic['SyncKey']
            self.synckey = '|'.join(["%s_%s" % (keyVal['Key'], keyVal['Val']) for keyVal in self.SyncKey['List']])
        return dic['AddMsgList']

    def send_message(self, word, user_openid):
        url = self.base_uri + '/webwxsendmsg?pass_ticket=%s' % self.pass_ticket
        clientMsgId = str(int(time.time() * 1000)) + str(random.random())[:5].replace('.', '')

        r = requests.post(url, json={'BaseRequest': self.BaseRequest,
                                     'Msg': {"Type": 1,
                                             "Content": self._transcoding(word),
                                             "FromUserName": self.User['UserName'],
                                             "ToUserName": user_openid,
                                             "LocalID": clientMsgId,
                                             "ClientMsgId": clientMsgId
                                             }
                                     })
        dic = r.json()
        return dic['BaseResponse']['Ret'] == 0

    def get_group_name(self, openid):
        if openid in self.groups:
            return self.groups[openid]['nick']
        self.update_group_info(openid)
        return self.groups[openid]['nick']

    def get_readable_name(self, openid):
        if openid == self.User['UserName']:
            return self.User['NickName']  # 自己
        if openid in self.friends:
            return self.friends[openid].get('remark', None) or self.friends[openid]['nick']

        if openid[:2] == '@@':
            # 群
            return self.get_group_name(openid)
        if openid in self.group_friends:
            # 群友
            return self.group_friends[openid].get('remark', None) or self.group_friends[openid]['nick']

        return "Unknown"

    def get_openid(self, name):
        for k, v in self.friends.iteritems():
            if name == v['remark'] or name == v['nick']:
                return k

        return None

    def show_text_message(self, message):
        src = self.get_readable_name(message['FromUserName'])
        dst = self.get_readable_name(message['ToUserName'])
        content = message['Content'].replace('&lt;', '<').replace('&gt;', '>')

        if message['MsgType'] == 1:
            if message['FromUserName'][:2] == '@@':
                logger.debug("re result:<%s> from %s", global_re_keywords.findall(content.decode('utf-8')), content)

                # 接收到来自群的消息
                if ":<br/>" in content:
                    [people, content] = content.split(':<br/>', 1)
                    speaker = self.get_readable_name(people)
                    content = content.replace('<br/>', '\n')
                    logger.info('[%s] %s:<%s>' % (src.strip(), speaker.strip(), content))
                    if global_re_keywords.findall(content.decode('utf-8')):
                        message_logger.info('!!![%s] %s:<%s>' % (src.strip(), speaker.strip(), content))
                        data = {"text": "[%s]%s: %s" % (src.strip(), speaker.strip(), content)}
                        SHARE_Q.put(data)
            else:
                message_logger.info('!!!%s -> %s: %s' % (src.strip(), dst.strip(), content.replace('<br/>', '\n')))
                if message['FromUserName'] != self.User['UserName']:  # not self sent.
                    data = {"text": "%s: %s" % (src.strip(), content.replace('<br/>', '\n'))}
                    SHARE_Q.put(data)
        else:
            logger.debug("unknown message,%s->%s:%s,file?<%s>", src, dst, content, message.get("FileName", "nofile"))

    def handle_messages(self, message_list):
        for msg in message_list:
            self.show_text_message(msg)

    def sync_message(self):
        logger.info('[*] 进入消息监听模式 ... 成功')
        self._run('[*] 进行同步线路测试 ... ', self.check_wexin_hosts)

        configure_monitor = Thread(target=set_keywords)
        configure_monitor.setDaemon(True)
        configure_monitor.start()
        logger.info("keywords monitor started.")

        push_to_slack = Thread(target=worker_send_message_to_slack)
        push_to_slack.setDaemon(True)
        push_to_slack.start()
        logger.info("slack message worker started.")

        while True:
            self.last_check = time.time()
            [retcode, selector] = self.synccheck()

            if retcode == '1100':
                logger.debug('[*] 你在手机上登出了微信，再见')
                break
            elif retcode == '1101':
                logger.debug('[*] 你在其他地方登录了 WEB 版微信，再见')
                break
            else:  # retcode == '0':
                if selector == '2':  # new messages
                    logger.info('new messages')
                    for msg in self.retrieve_messages():
                        self.show_text_message(msg)
                        # self.handle_messages()
                else:  # selector == '0':
                    time.sleep(1)

            if (time.time() - self.last_check) <= 20:
                time.sleep(time.time() - self.last_check)

    def send_message_by_nick(self, nick, word):
        user_openid = self.get_openid(nick)
        if user_openid:
            if not self.send_message(word, user_openid):
                logger.error("send message to %s failed.", nick)
        else:
            logger.error('[*] 此用户不存在')

    def send_to_all(self, word):
        for contact in self.friends.keys():
            if not self.send_message(word, contact['UserName']):
                logger.error("send message to %s failed.",
                             contact['RemarkName'] if contact['RemarkName'] else contact['NickName'])
            time.sleep(1)

    @catchKeyboardInterrupt
    def start(self):
        logger.info('[*] 微信网页版 ... 开动')
        while True:
            self._run('[*] 正在获取 uuid ... ', self.get_wechat_uuid)
            self.gen_qrcode()
            logger.info('[*] 请使用微信扫描二维码以登录 ...')
            if not self.wait_for_login():
                logger.info('[*] 请在手机上点击确认以登录 ...')
                continue
            if not self.wait_for_login(0):
                continue
            break

        self._run('[*] 正在登录 ... ', self.login)
        self._run('[*] 微信初始化 ... ', self.init_web_weixin)
        self._run('[*] 开启状态通知 ... ', self.handle_status_notification)
        self._run('[*] 获取联系人 ... ', self.get_contacts)

        # logger.debug(self)
        logger.debug("self info:%s", self.User)

        message_monitor = multiprocessing.Process(target=self.sync_message)
        message_monitor.start()

        while True:
            text = raw_input('')
            if text == 'quit':
                message_monitor.terminate()
                logger.info('[*] 退出微信')
                exit(0)
            elif text[:2] == '->':
                [name, word] = text[2:].split(':')
                if name == 'all':
                    self.send_to_all(word)
                else:
                    self.send_message_by_nick(name, word)

    def _run(self, str, func, *args):
        logger.debug(str)
        if func(*args):
            logger.debug('%s... 成功' % (str))
        else:
            logger.debug('%s... 失败' % (str))
            logger.debug('[*] 退出程序')
            exit(1)

    def _printQR(self, mat):
        for i in mat:
            BLACK = '\033[40m  \033[0m'
            WHITE = '\033[47m  \033[0m'
            print ''.join([BLACK if j else WHITE for j in i])

    def _transcoding(self, data):
        if not data:
            return data
        result = None
        if type(data) == unicode:
            result = data
        elif type(data) == str:
            result = data.decode('utf-8')
        return result

    def _get(self, url, api=None):
        request = urllib2.Request(url=url)
        request.add_header('Referer', 'https://wx.qq.com/')
        if api == 'webwxgetvoice':
            request.add_header('Range', 'bytes=0-')
        if api == 'webwxgetvideo':
            request.add_header('Range', 'bytes=0-')
        try:
            response = urllib2.urlopen(request)
            data = response.read()
            # logging.debug(url)
            return data
        except urllib2.HTTPError, e:
            logger.error('HTTPError = ' + str(e.code))
        except urllib2.URLError, e:
            logger.error('URLError = ' + str(e.reason))
        except httplib.HTTPException, e:
            logger.error('HTTPException')
        except Exception:
            import traceback
            logger.error('generic exception: ' + traceback.format_exc())
        return ''

    def _post(self, url, params, jsonfmt=True):
        # logger.debug("%s,%s,cookie:%s", url, params, self.cookie)
        if jsonfmt:
            request = urllib2.Request(url=url, data=json.dumps(params))
            request.add_header('ContentType', 'application/json; charset=UTF-8')
        else:
            request = urllib2.Request(url=url, data=urllib.urlencode(params))

        try:
            response = urllib2.urlopen(request)
            data = response.read()
            if jsonfmt:
                return json.loads(data, object_hook=_decode_dict)
            return data
        except urllib2.HTTPError, e:
            logger.error('HTTPError = ' + str(e.code))
        except urllib2.URLError, e:
            logger.error('URLError = ' + str(e.reason))
        except httplib.HTTPException, e:
            logger.error('HTTPException')
        except Exception:
            import traceback
            logger.error('generic exception: ' + traceback.format_exc())

        return ''

    def _searchContent(self, key, content, fmat='attr'):
        if fmat == 'attr':
            pm = re.search(key + '\s?=\s?"([^"<]+)"', content)
            if pm:
                return pm.group(1)
        elif fmat == 'xml':
            pm = re.search('<{0}>([^<]+)</{0}>'.format(key), content)
            if not pm:
                pm = re.search(
                    '<{0}><\!\[CDATA\[(.*?)\]\]></{0}>'.format(key), content)
            if pm:
                return pm.group(1)
        return '未知'


class MyLogFormatter(logging.Formatter):
    """
    Inspired by
    `tornado <http://www.tornadoweb.org/en/stable/log.html?highlight=logformatter#tornado.log.LogFormatter>`_.
    """

    converter = time.gmtime

    DEFAULT_FORMAT = '[%(levelname)1.1s %(asctime)s.%(msecs)03dZ %(module)s:%(lineno)d] %(message)s'
    DEFAULT_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

    def __init__(self, fmt=DEFAULT_FORMAT, datefmt=DEFAULT_DATE_FORMAT):
        super(MyLogFormatter, self).__init__(fmt=fmt, datefmt=datefmt)


if __name__ == '__main__':
    logging.config.dictConfig({'version': 1,
                               'disable_existing_loggers': True,  # 'incremental': False,
                               'formatters': {'myformatter': {'()': MyLogFormatter,
                                                              },
                                              'messages': {
                                                  'format': '[%(levelname)1.1s %(asctime)s]: \n--->%(message)s',
                                                  'datefmt': '%Y-%m-%d %H:%M:%S'
                                              }
                                              },
                               'handlers': {'console': {'class': 'logging.StreamHandler',
                                                        'formatter': 'myformatter'
                                                        },
                                            'file_tmp': {'class': 'logging.FileHandler',
                                                         'filename': '/tmp/wexinweb.log',
                                                         'formatter': 'myformatter'
                                                         },
                                            'message_wexin': {'class': 'logging.FileHandler',
                                                              'filename': '/tmp/wexin_message.log',
                                                              'formatter': 'messages'
                                                              }

                                            },
                               'loggers': {'root': {'handlers': ['console', 'file_tmp'],
                                                    'propagate': False,
                                                    'level': 'DEBUG'
                                                    },
                                           'message_logger': {'handlers': ['console', 'message_wexin'],
                                                              'propagate': False,
                                                              'level': 'INFO'
                                                              },
                                           }
                               })
    logger = logging.getLogger('root')
    logger.setLevel("DEBUG")
    message_logger = logging.getLogger('message_logger')
    if not sys.platform.startswith('win'):
        import coloredlogs

        coloredlogs.install(level='DEBUG')

    WebWeixin().start()
