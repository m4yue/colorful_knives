#!/usr/bin/env python
# coding: utf-8

import requests
from redis import StrictRedis

red_conn = StrictRedis(db=15)
req_ss = requests.session()
