#!/usr/bin/env python
# coding: utf-8

import time
import logging
import logging.config


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
