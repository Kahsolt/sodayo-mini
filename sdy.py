#!/usr/bin/env python3
# Author: Armit
# Create Time: 2021/09/24 

import os
from pwd import getpwuid
from argparse import ArgumentParser

import requests as R

from settings import *


__version__ = '0.1'     # 2021/09/26


def sync():
  try:
    d = R.put(f'{API_BASE}/sync', timeout=30).json()
    if d["ok"]: print('ok')
    else:      print(f'[error] {d["reason"]}')
  except Exception as e:
    print(e)


def runtime():
  try:
    d = R.get(f'{API_BASE}/runtime').json()
    if d["ok"]:
      for hostname, gpu_rt in d["data"].items():
        print(f'<{hostname}>')
        for gpu_id, users in gpu_rt.items():
          print(f'  [{gpu_id}]: {",".join(sorted(users))}')
    else:
      print(f'[error] {d["reason"]}')
  except Exception as e:
    print(e)


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
  parser.add_argument('--sync',    action='store_true',   help='force sync data from all hosts')
  parser.add_argument('--runtime', action='store_true',   help='show latest runtime info')
  parser.add_argument('--quota', type=str, default='@me', help='query quota remnants, eg. --quota @me/@all/somebody')
  args = parser.parse_args()

  username = getpwuid(os.getuid()).pw_name
  if args.sync: sync()
  elif args.runtime: runtime()
  elif args.quota:
    if args.quota == '@all': quota()
    elif args.quota == '@me': quota(username)
    else: quota(args.quota)
