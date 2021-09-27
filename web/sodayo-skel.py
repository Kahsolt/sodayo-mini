#!/usr/bin/env python3
# Author: Armit
# Create Time: 2021/09/25 

import os
from random import random, randrange, sample
from typing import Union
from collections import defaultdict
from traceback import format_exc

from flask import Flask, jsonify, request, render_template
from flask_cors import CORS


__version__ = '0.1'     # 2021/09/25


# NOTE: this is a dummy sodayo-server for frontend develop/test

WEB_CHROOT_PATH = 'dist'

##############################################################################
# globals

os.chdir(WEB_CHROOT_PATH)
app = Flask(__name__, template_folder='', static_folder='')
CORS(app, support_credential=True)

gpu_runtime = defaultdict(lambda:defaultdict(set))
gpu_runtime['server1'][0] = {'yesbody'}
gpu_runtime['server1'][1] = {}
gpu_runtime['server2'][0] = {'nobody', 'yesbody'}
gpu_runtime['server2'][1] = {'nobody'}
gpu_runtime['server2'][2] = {'yesbody'}
gpu_runtime['server3'][0] = {}
gpu_runtime['server3'][1] = {}
gpu_runtime['server3'][2] = {'somebody'}
gpu_runtime['server3'][3] = {}


##############################################################################
# utils

class RESPONSE:

  def make(ok:int=False, data:Union[dict, list]=None, reason:str=None) -> str:
    r = { 'ok': ok }
    if data is not None: r['data'] = data
    if reason is not None: r['reason'] = reason
    return jsonify(r)

  ok = lambda data: RESPONSE.make(ok=True, data=data)
  fail = lambda reason: RESPONSE.make(ok=False, reason=reason)


##############################################################################
# HTTP routes (jsonstr in, jsonstr out)

@app.route('/', methods=['GET'])
def root():
  try:    return render_template('index.html')
  except: return 'Web service not available :('

@app.route('/runtime', methods=['GET'])
def runtime():
  return RESPONSE.ok({k: {i: list(u) for i, u in v.items()} for k, v in gpu_runtime.items()})

@app.route('/quota', methods=['GET'])
def quota():
  username = request.args.get('username')

  try:
    quotas = {
      'yesbody': 233,
      'nobody': -120,
      'somebody': 50,
    }
    if not username: return RESPONSE.ok(quotas)
    else:
      if username in quotas: return RESPONSE.ok({username: quotas[username]})
      else: return RESPONSE.fail(f'username {username!r} not found')
  except Exception as e:
    print(format_exc())
    return RESPONSE.fail(f'server internal error: {e}')

@app.route('/realloc', methods=['POST'])
def realloc():
  try:
    data = request.json
    username = data.get('username')
    password = data.get('password')
    gpu_count = int(data.get('gpu_count'))
    assert None not in [username, password, gpu_count]
  except:
    print(format_exc())
    return RESPONSE.fail('parameter wrong')
  
  try:
    x = random()
    if   x < 0.1: r = 'wrong username/password'
    elif x < 0.3: r = 'resource not available'
    else:         r = {'hostname': f'server{randrange(5)}', 'gpu_ids': sorted(sample(list(range(8)), gpu_count))}
    return type(r) == str and RESPONSE.fail(r) or RESPONSE.ok(r)
  except Exception as e:
    print(format_exc())
    return RESPONSE.fail(f'server internal error: {e}')


##############################################################################
# main entry

if __name__ == '__main__':
  try:
    app.run(host='127.0.0.1', port=2333, debug=False)
  except KeyboardInterrupt:
    pass
