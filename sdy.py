#!/usr/bin/env python3
# Author: Armit
# Create Time: 2021/09/24 

import os
from json import dumps
from pwd import getpwuid
from argparse import ArgumentParser

import requests as R

from settings import *


__version__ = '0.1'     # 2021/09/26


def quota(username=None):
  try:
    d = R.get(f'{API_BASE}/quota' + (username and f'?username={username}' or '')).json()
    if d["ok"]:
      for k, v in d["data"].items():
        print(f'{(k + ":").ljust(10)}{v:.2f} hours')    # NOTE: maxlen of username is about 7
    else:
      print(f'[error] {d["reason"]}')
  except Exception as e:
    print(e)


if __name__ == '__main__':
  parser = ArgumentParser()
  parser.add_argument('--quota', type=str, default='@me', help='query quota, eg. --quota @me/@all/somebody')
  args = parser.parse_args()

  username = getpwuid(os.getuid()).pw_name
  if args.quota:
    if args.quota == '@all': quota()
    elif args.quota == '@me': quota(username)
    else: quota(args.quota)
