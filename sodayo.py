#!/usr/bin/env python3
# Author: Armit
# Create Time: 2021/09/23 

import os
import logging
from re import compile as Regex
from shutil import copy2
from threading import Timer, RLock
from time import time
from json import loads
from datetime import datetime
from random import sample, shuffle
from collections import defaultdict
from typing import DefaultDict, Union
from traceback import format_exc
from pwd import getpwuid

from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import paramiko
from paramiko.ssh_exception import AuthenticationException

from settings import *


__version__ = '0.1'     # 2021/09/26


# NOTE: main functional code lies in `GpuMonitor.dequota_task()` and `GpuMonitor.alloc_gpu()`

##############################################################################
# globals

os.chdir(WEB_CHROOT_PATH)
app = Flask(__name__, template_folder='', static_folder='')
#app.after_request(after_request)
CORS(app, support_credential=True, resources={r'/*': {'origins': '*'}})

#def after_request(resp):
#  resp.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin') or '*'
#  resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,'
#  resp.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization,Accept,Origin,Referer,User-Agent'
#  resp.headers['Access-Control-Allow-Credentials'] = 'true'
#  return resp

host_resolv = { }           # {'hostname': sock(hist:str, port:int)}, for ssh and kill
gpu_runtime = defaultdict(lambda:defaultdict(set))    # {'hostname': {0: {usernames}}}

logger = None
monitor = None
lock = RLock()              # for use `ssh` client


##############################################################################
# utils

def init_logger():
  global logger

  logger = logging.getLogger(__name__)
  logger.setLevel(level=logging.DEBUG)

  log = paramiko.util.get_logger("paramiko")
  log.setLevel(logging.CRITICAL)

  if LOG_FILE:
    lf = logging.FileHandler(os.path.join(BASE_PATH, LOG_FILE), encoding='utf8')
    lf.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(lineno)s: %(message)s"))
    lf.setLevel(logging.INFO)
    logger.addHandler(lf)

  if DEBUG_MODE:
    con = logging.StreamHandler()
    con.setFormatter(logging.Formatter("[%(levelname)s] %(lineno)s: %(message)s"))
    con.setLevel(logging.DEBUG)
    logger.addHandler(con)

class RESPONSE:

  def make(ok:int=False, data:Union[dict, list]=None, reason:str=None) -> str:
    r = { 'ok': ok }
    if data is not None: r['data'] = data
    if reason is not None: r['reason'] = reason
    return jsonify(r)

  ok = lambda data=None: RESPONSE.make(ok=True, data=data)
  fail = lambda reason='': RESPONSE.make(ok=False, reason=reason)

min_to_sec = lambda x: x * 60

now_ts = lambda: datetime.timestamp(datetime.now())


##############################################################################
# workers

def perf_counter(fn):
  def wrapper(self, *args, **kwargs):
    start = time()
    r = fn(self, *args, **kwargs)
    end = time()
    logger.debug(f'[perf_counter]: {fn.__name__} {end - start:.4f}s')
    return r
  return wrapper

def check_rotate(fn):
  def wrapper(self, *args, **kwargs):
    if self.current_fp != self._get_fp():
      self.rotate()
    return fn(self, *args, **kwargs)
  return wrapper

def with_lock(lock:RLock):
  def wrapper(fn):
    def wrapper(self, *args, **kwargs):
      lock.acquire()
      r = fn(self, *args, **kwargs)
      lock.release()
      return r
    return wrapper
  return wrapper

class QuotaTracker:

  WHITESPACE_REGEX = Regex(r'\s+')

  quota_info = { }    # 'username': time(int)
  
  def _get_fp(self) -> str:
    return os.path.join(BASE_PATH, DATA_PATH, f'quota_{datetime.now().strftime("%Y-%m")}.txt')

  def __init__(self):
    # the file (abspath) that associated with current `quota_info`
    self.current_fp = None
    self.dump_timer = Timer(min_to_sec(DUMP_INTERVAL // 2), self.dump_task)
  
  def start(self):
    self.rotate()
    self.dump_timer.start()

  def stop(self):
    self.dump_timer.cancel()
    self.dump()

  def load(self):
    logger.info(f'[load] from {self.current_fp}')

    with open(self.current_fp, 'r', encoding='utf8') as fh:
      for line in fh.read().split('\n'):
        if line.startswith('#') or not line.strip(): continue
        try:
          username, quota = self.WHITESPACE_REGEX.sub(' ', line.strip()).split(' ')
          self.quota_info[username] = float(quota)
        except:
          logger.warning(f' << cannot parse line {line!r}, ignored')
  
  def dump(self):
    logger.info(f'[dump] to {self.current_fp}')

    with open(self.current_fp, 'w', encoding='utf8') as fh:
      for username, quota in self.quota_info.items():
        fh.write(f'{username} {quota:.4f}\n')
  
  def rotate(self):
    logger.info('[rotate]')

    # if current `quota_info` is already associated, dump to that file
    if self.current_fp: self.dump()

    # rotate to new file
    self.current_fp = self._get_fp()
    # absence indicates a new month beginning, let's make a new copy from `quota_init`
    if not os.path.exists(self.current_fp):
      os.makedirs(os.path.join(BASE_PATH, DATA_PATH), exist_ok=True)
      copy2(os.path.join(BASE_PATH, QUOTA_INIT_FILE), self.current_fp)
    
    # load `quota_info` from file
    self.load()

  @check_rotate
  def dequota(self, username:str, time:int):
    if username in self.quota_info:
      h = time / 60     # NOTE: time is in minutes
      logger.info(f'  >> user {username!r} of {h:.4f} hour(s)')
      self.quota_info[username] -= h
    else:
      logger.warning(f'  << user {username!r} is beyond track, ignored')

  @check_rotate
  def query(self) -> dict:
    return self.quota_info

  def dump_task(self):
    # reset timer
    self.dump_timer = Timer(min_to_sec(DUMP_INTERVAL), self.dump_task)
    self.dump_timer.start()

    # do work
    self.dump()

class GpuMonitor:

  def __init__(self):
    # quota tracker
    self.quota = QuotaTracker()

    # last sync timestamp
    self.last_sync_ts = now_ts()

    # ssh configs
    self.ssh = paramiko.SSHClient()
    self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    self.username = getpwuid(os.getuid()).pw_name
    self.pkey = paramiko.RSAKey.from_private_key_file(os.path.join(os.path.expanduser('~'), '.ssh/id_rsa'))

    self.check_timer = Timer(0, self.dequota_task)

  def start(self):
    self.quota.start()
    self.check_timer.start()

  def stop(self):
    self.check_timer.cancel()
    self.quota.stop()

  @with_lock(lock)
  def sync(self, collect_quota=False) -> Union[DefaultDict, bool]:
    now_ts_freeze = now_ts()
    if not collect_quota and (now_ts_freeze - self.last_sync_ts <= SYNC_DEADTIME): return False
    self.last_sync_ts = now_ts_freeze

    if collect_quota:
      quota_portion = defaultdict(int)     # {'username': portion(int)}
    for host, port in TRACKED_SOCKETS:      # foreach host
      logger.info(f'  >> query ({host}, {port})')

      try:
        self.ssh.connect(hostname=host, port=port, username=self.username, pkey=self.pkey,
                         timeout=10, banner_timeout=10, auth_timeout=10)

        # NOTE: dict key 'queyr_time' should be removed, cos' type `datetime` is not JSON serializable
        # but `del['queyr_time']` does NOT work due to some `eval()` function closure issue, so we keep this `pop()[1]` magic :)
        py_cmd = 'import gpustat, json; r = gpustat.new_query().jsonify(); r.pop(list(r.keys())[1]); print(json.dumps(r))'
        sh_cmd = f'python -c "{py_cmd}"'
        stdin, stdout, stderr = self.ssh.exec_command(sh_cmd, timeout=15)
        res = loads(stdout.read().strip())

        hostname = res['hostname']
        if hostname not in host_resolv:
          host_resolv[hostname] = (host, port)

        gpu_rt = gpu_runtime[hostname]    # {0: {username}}
        for gpu in res['gpus']:           # foreach GPU
          gpu_id, procs = gpu['index'], gpu['processes']
          gpu_rt[gpu_id] = {p['username'] for p in procs}

          if collect_quota:
            for username in gpu_rt[gpu_id]:
              if username == 'root': continue
              quota_portion[username] += 1

      except Exception as e:
        logger.error(f'  << failed for ({host}, {port})')
        logger.debug(e)
      finally:
        self.ssh.close()

    if collect_quota: return quota_portion
    else: return True

  @perf_counter       # ~ 6s
  def dequota_task(self):
    logger.info('[dequota_task]')

    # reset timer
    self.check_timer = Timer(min_to_sec(SYNC_INTERVAL), self.dequota_task)
    self.check_timer.start()

    # do work
    quota_portion = self.sync(collect_quota=True)
    if quota_portion:
      # NOTE: we move this log out of `QuotaTracker.dequota` for pretty printing :)
      logger.info('[dequota]')
      for username, portion in quota_portion.items():
        self.quota.dequota(username, SYNC_INTERVAL * portion)

  @with_lock(lock)
  def alloc_gpu(self, username, password, gpu_count) -> Union[str, list]:
    logger.info('[alloc_gpu]')

    # try alloc current free
    free_map = {hostname: {gpu_id for gpu_id, users in gpu_rt.items() if not len(users)}
                for hostname, gpu_rt in gpu_runtime.items()}
    hostnames = list(free_map.keys()); shuffle(hostnames)
    for hostname in hostnames:
      free_gpu_ids = list(free_map[hostname])
      if len(free_gpu_ids) >= gpu_count:
        data = {
          'hostname': hostname,
          'gpu_ids': sorted(sample(free_gpu_ids, gpu_count))
        }
        return data

    # check quota of requester
    quotas = self.quota.query()
    if username in quotas and quotas[username] < 0:
      return 'you have run out of quota'
    
    # try alloc with kill
    def all_killable(users):
      for user in users:
        if user in quotas and quotas[user] > 0:
          return False
      return True

    killable_map = {hostname: {gpu_id for gpu_id, users in gpu_rt.items() if all_killable(users)}
                    for hostname, gpu_rt in gpu_runtime.items()}
    hostnames = list(killable_map.keys()); shuffle(hostnames)
    for hostname in hostnames:
      if len(killable_map[hostname]) >= gpu_count:
        free_gpu_ids = list(free_map[hostname])
        killable_gpu_ids = list(killable_map[hostname] - free_map[hostname])
        to_kill_cnt = gpu_count - len(free_gpu_ids)
        to_kill_gpu_ids = sample(killable_gpu_ids, to_kill_cnt)

        logger.info('[kill]')
        try:
          host, port = host_resolv[hostname]
          self.ssh.connect(hostname=host, port=port, username=username, password=password,
                           timeout=10, banner_timeout=10, auth_timeout=10)

          py_cmd = 'import gpustat, json; r = gpustat.new_query().jsonify(); r.pop(list(r.keys())[1]); print(json.dumps(r))'
          sh_cmd = f'python -c "{py_cmd}"'
          stdin, stdout, stderr = self.ssh.exec_command(sh_cmd, timeout=15)
          res = loads(stdout.read().strip())

          for gpu in res['gpus']:           # foreach GPU
            gpu_id = gpu['index']
            if gpu_id not in to_kill_gpu_ids: continue
            for proc in gpu['processes']:
              pid = proc['pid']
              logger.info(f'  >> [{proc["username"]}] {pid}: {proc["command"]}')

              sh_cmd = f'kill -9 {pid}'
              stdin, stdout, stderr = self.ssh.exec_command(sh_cmd, timeout=15)
              r = stdout.read()

        except AuthenticationException:
          return 'linux auth failed, wrong username/password'
        except:
          logger.error(format_exc())
          return 'server internal error'
        finally:
          self.ssh.close()
        
        data = {
          'hostname': hostname,
          'gpu_ids': sorted(free_gpu_ids + to_kill_gpu_ids)
        }
        return data

    return 'lack of resource'


##############################################################################
# HTTP routes (jsonstr in, jsonstr out)

@app.route('/', methods=['GET'])
def root():
  try:    return render_template('index.html')
  except: return 'Web service not available :('

@app.route('/sync', methods=['PUT'])
def sync():
  r = monitor.sync()
  return r and RESPONSE.ok() or RESPONSE.fail('server busy, retry later')

@app.route('/runtime', methods=['GET'])
def runtime():
  d = {k: {i: list(u) for i, u in v.items()} for k, v in gpu_runtime.items()}
  return RESPONSE.ok(d)

@app.route('/quota', methods=['GET'])
def quota():
  username = request.args.get('username')

  try:
    quotas = monitor.quota.query()
    if not username: return RESPONSE.ok(quotas)
    else:
      if username in quotas: return RESPONSE.ok({username: quotas[username]})
      else: return RESPONSE.fail(f'username {username!r} not found')
  except:
    logger.error(format_exc())
    return RESPONSE.fail('server internal error')

@app.route('/realloc', methods=['POST'])
def realloc():
  try:
    data = request.json
    username = data.get('username')
    password = data.get('password')
    gpu_count = int(data.get('gpu_count'))
    assert None not in [username, password, gpu_count]
  except:
    return RESPONSE.fail('parameter wrong')
  
  try: 
    r = monitor.alloc_gpu(username, password, gpu_count)
    return type(r) == str and RESPONSE.fail(r) or RESPONSE.ok(r)
  except:
    logger.error(format_exc())
    return RESPONSE.fail('server internal error')


##############################################################################
# main entry

if __name__ == '__main__':
  init_logger()
  monitor = GpuMonitor()
  
  try:
    monitor.start()
    host, port = BIND_SOCKET
    app.run(host=host, port=port, debug=False)
  except KeyboardInterrupt:
    logger.info('exit by Ctrl+C')
  except Exception:
    logger.error(format_exc())
  finally:
    monitor.stop()
