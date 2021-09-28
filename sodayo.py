#!/usr/bin/env python3
# Author: Armit
# Create Time: 2021/09/23 

import os
import logging
from re import compile as Regex
from json import loads
from shutil import copy
from time import time
from threading import Timer, RLock
from datetime import datetime
from base64 import b64decode
from random import sample, shuffle
from collections import defaultdict, deque
from typing import DefaultDict, Union, Tuple
from traceback import format_exc
from pwd import getpwuid

from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import paramiko
from paramiko.client import SSHClient
from paramiko.ssh_exception import AuthenticationException, SSHException

from settings import *


__version__ = '0.1'     # 2021/09/27


# NOTE: main functional code lies in `sync()` and `alloc_gpu()` of `GpuMonitor`

##############################################################################
# globals

os.chdir(WEB_CHROOT_PATH)   # NOTE: chroot before `app` define
app = Flask(__name__, template_folder='', static_folder='')
CORS(app, support_credential=True, resources={r'/*': {'origins': '*'}})

host_resolv = { }           # {'hostname': sock(hist:str, port:int)}, for ssh to kill
gpu_runtime = defaultdict(lambda:defaultdict(set))    # {'hostname': {0: {'username'}}}

logger = None
monitor = None
lock = RLock()              # global lock, may be useful in cases ...


##############################################################################
# utils

def init_logger():
  global logger

  logger = logging.getLogger(__name__)
  logger.setLevel(level=logging.DEBUG)

  log = paramiko.util.get_logger("paramiko")    # NOTE: suppress detailed paramiko logs
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
  fail = lambda reason=None: RESPONSE.make(ok=False, reason=reason)

min_to_sec  = lambda x: x * 60
min_to_hour = lambda x: x / 60
now_ts = lambda: datetime.timestamp(datetime.now())

sock_to_hostport = lambda sock: f'{sock[0]}:{sock[1]}'

def to_serializable(data):
  if data is None:
    return None
  elif type(data) in [int, float, str]:
    return data
  elif type(data) in [list, tuple, set, deque]:
    return [to_serializable(v) for v in data]
  elif type(data) in [dict, defaultdict]:
    return {to_serializable(k): to_serializable(v) for k, v in data.items()}
  else:
    return repr(data)


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

  quota_info = { }    # 'username': time_remnants(float)
  
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
  
  @with_lock(lock)
  def rotate(self):
    logger.info('[rotate]')

    # if current `quota_info` is already associated, dump to that file
    if self.current_fp: self.dump()

    # rotate to new file
    self.current_fp = self._get_fp()
    # absence indicates a new month beginning, let's make a new copy from `quota_init`
    if not os.path.exists(self.current_fp):
      os.makedirs(os.path.join(BASE_PATH, DATA_PATH), exist_ok=True)
      copy(os.path.join(BASE_PATH, QUOTA_INIT_FILE), self.current_fp)
      
    # load `quota_info` from file
    self.load()

  @check_rotate
  def dequota(self, username:str, time_in_hour:float):
    if username in self.quota_info:
      logger.info(f'  >> user {username!r} of {time_in_hour:.4f} hour(s)')
      self.quota_info[username] -= time_in_hour
    else:
      logger.warning(f'  << user {username!r} is beyond track, ignored')

  @check_rotate
  def query(self) -> dict:
    return self.quota_info        # NOTE: use `.copy()` if security signifies

  def dump_task(self):
    # reset timer
    self.dump_timer = Timer(min_to_sec(DUMP_INTERVAL), self.dump_task)
    self.dump_timer.start()

    # do work
    self.dump()

class SshPool:

  SYSTEM_USERNAME = getpwuid(os.getuid()).pw_name
  SYSTEM_PKEY = paramiko.RSAKey.from_private_key_file(os.path.join(os.path.expanduser('~'), '.ssh/id_rsa'))

  def __init__(self):
    self.pool = { }         # { sock(str,int): SSHClient }
  
  def destroy(self):
    for ssh in self.pool.values():
      ssh.close()
    self.pool.clear()

  @staticmethod
  def new() -> SSHClient:
    logger.info('[SshPool.new]')

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    return ssh
  
  @staticmethod
  @with_lock(lock)
  def test_login(sock, username, password) -> bool:
    logger.info('[SshPool.test_login]')

    try:
      host, port = sock
      ssh = SshPool.new()
      ssh.connect(hostname=host, port=port, username=username, password=password,
                  banner_timeout=SSH_TIMEOUT)
    except AuthenticationException:
      return False
    except:
      logger.error(format_exc())
      return None
    else:
      return True
    finally:
      ssh.close()

  def get(self, sock:Tuple[str, int]) -> SSHClient:
    if sock not in self.pool:
      host, port = sock
      try:
        ssh = SshPool.new()
        ssh.connect(hostname=host, port=port, username=self.SYSTEM_USERNAME, pkey=self.SYSTEM_PKEY,
                    banner_timeout=SSH_TIMEOUT)
        sh_cmd = 'hostname'   # just for a test
        stdin, stdout, stderr = ssh.exec_command(sh_cmd, timeout=SSH_TIMEOUT)
        _ = stdout.read().strip()
      except:
        pass
      else:
        self.pool[sock] = ssh

    return self.pool.get(sock)

  def mark_broken(self, ssh:SSHClient):
    logger.info('[SshPool.mark_broken]')

    for k, v in self.pool.items():
      if ssh == v:
        ssh.close()
        self.pool.pop(k)
        break

class GpuMonitor:

  def __init__(self):
    # workers
    self.quota_tracker = QuotaTracker()
    self.ssh_pool      = SshPool()
    self.check_timer   = Timer(1, self.dequota_task)

    # limit `.sync()` call frequency
    self.last_sync_ts = now_ts()

  def start(self):
    self.quota_tracker.start()
    self.check_timer.start()

  def stop(self):
    self.check_timer.cancel()
    self.ssh_pool.destroy()
    self.quota_tracker.stop()

  def query_quota(self, username=None) -> dict:
    r = self.quota_tracker.query()
    if username:
      if username in r: return {username: r[username]}
      else: return None
    else:
      return r

  @perf_counter
  def try_sync(self) -> bool:
    if now_ts() - self.last_sync_ts < FORCE_SYNC_DEADTIME:
      return False

    self.sync()
    self.last_sync_ts = now_ts()
    return True

  @with_lock(lock)
  def sync(self) -> DefaultDict:
    quota_portion = defaultdict(int)     # {'username': portion(int)}
    for sock in TRACKED_SOCKETS:         # foreach host
      logger.info(f'  >> query {sock_to_hostport(sock)}')

      try:
        ssh = self.ssh_pool.get(sock)
  
        # NOTE: dict key 'queyr_time' should be removed, cos' type `datetime` is not JSON serializable
        # but `del['queyr_time']` does NOT work due to some `eval()` function closure issues, so we keep this `pop()[1]` magic :)
        py_cmd = 'import gpustat, json; r = gpustat.new_query().jsonify(); r.pop(list(r.keys())[1]); print(json.dumps(r))'
        sh_cmd = f'python -c "{py_cmd}"'
        stdin, stdout, stderr = ssh.exec_command(sh_cmd, timeout=SSH_TIMEOUT)
        res = loads(stdout.read().strip())

        hostname = res['hostname']
        if hostname not in host_resolv:
          host_resolv[hostname] = sock

        gpu_rt = gpu_runtime[hostname]    # {0: {username}}
        for gpu in res['gpus']:           # foreach GPU
          gpu_id, procs = gpu['index'], gpu['processes']
          gpu_rt[gpu_id] = {p['username'] for p in procs}     # dedup users on a single card

          for username in gpu_rt[gpu_id]:
            quota_portion[username] += 1

      except Exception:
        for k, v in host_resolv.items():    # temporarily forget it
          if v == sock and k in gpu_runtime:
            gpu_runtime.pop(k)
            break
        self.ssh_pool.mark_broken(ssh)
        logger.error(f'  << failed for {sock_to_hostport(sock)}')

    return quota_portion

  @perf_counter
  def dequota_task(self):
    logger.info('[dequota_task]')

    # reset timer
    self.check_timer = Timer(min_to_sec(AUTO_SYNC_INTERVAL), self.dequota_task)
    self.check_timer.start()

    # do work
    quota_portion = self.sync()
    if quota_portion:
      # NOTE: we move this log out of `QuotaTracker.dequota` for pretty printing :)
      logger.info('[dequota]')
      for username, portion in quota_portion.items():
        self.quota_tracker.dequota(username, min_to_hour(AUTO_SYNC_INTERVAL * portion))

  def alloc_gpu(self, username, password, gpu_count) -> Union[str, list]:
    logger.info('[alloc_gpu]')

    # try alloc current free
    free_map = {hostname: {gpu_id for gpu_id, users in gpu_rt.items() 
                                  if not len(users)}
                for hostname, gpu_rt in gpu_runtime.items()}
    hostnames = list(free_map.keys()); shuffle(hostnames)
    for hostname in hostnames:
      free_gpu_ids = list(free_map[hostname])
      if len(free_gpu_ids) >= gpu_count:
        return {
          'hostname': hostname,
          'gpu_ids': sorted(sample(free_gpu_ids, gpu_count))
        }

    # check quota of requester
    quotas = self.quota_tracker.query()
    if username in quotas and quotas[username] < 0:
      return 'you have run out of quota'

    # try alloc with kill
    all_killable = lambda users: not [True for user in users if user in quotas and quotas[user] > 0]
    killable_map = {hostname: {gpu_id for gpu_id, users in gpu_rt.items()
                                      if (gpu_id not in free_map[hostname]) and all_killable(users)}
                    for hostname, gpu_rt in gpu_runtime.items()}
    hostnames = list(killable_map.keys()); shuffle(hostnames)
    for hostname in hostnames:
      if len(free_map[hostname]) + len(killable_map[hostname]) >= gpu_count:
        sock = host_resolv[hostname]

        # check authentication
        r = SshPool.test_login(sock, username, password)
        if r is False:  return 'linux auth failed, wrong username/password'
        elif r is None: return 'server internal error: ssh connect failed'

        # decide which to sacrifice with randomness
        free_gpu_ids      = list(free_map[hostname])
        killable_gpu_ids  = list(killable_map[hostname])
        to_kill_cnt       = gpu_count - len(free_gpu_ids)
        to_kill_gpu_ids   = sample(killable_gpu_ids, to_kill_cnt)

        # gogogo!
        logger.info('[kill]')
        try:
          ssh = self.ssh_pool.get(sock)
          py_cmd = 'import gpustat, json; r = gpustat.new_query().jsonify(); r.pop(list(r.keys())[1]); print(json.dumps(r))'
          sh_cmd = f'python -c "{py_cmd}"'
          stdin, stdout, stderr = ssh.exec_command(sh_cmd, timeout=SSH_TIMEOUT)
          res = loads(stdout.read().strip())

          for gpu in res['gpus']:           # foreach GPU
            gpu_id = gpu['index']
            if gpu_id not in to_kill_gpu_ids: continue
            for proc in gpu['processes']:
              pid = proc['pid']
              logger.info(f'  >> [{proc["username"]}] {pid}: {proc["command"]}')

              sh_cmd = f'kill -9 {pid}'
              stdin, stdout, stderr = ssh.exec_command(sh_cmd, timeout=SSH_TIMEOUT)
              _ = stdout.read()              # may us assert _ is ''

        except Exception as e:
          logger.error(format_exc())
          return f'server internal error: {e}'
        
        # instantly make a sync
        Timer(0, self.sync).start()
        # tell client
        return {
          'hostname': hostname,
          'gpu_ids': sorted(free_gpu_ids + to_kill_gpu_ids)
        }

    return 'lack of resource'


##############################################################################
# HTTP routes

@app.route('/', methods=['GET'])
def root():
  try:    return render_template('index.html')
  except: return 'Web service not available :('

@app.route('/sync', methods=['PUT'])
def sync():
  r = monitor.try_sync()
  return r and RESPONSE.ok() or RESPONSE.fail('server busy, retry later')

@app.route('/runtime', methods=['GET'])
def runtime():
  r = to_serializable(gpu_runtime)
  return RESPONSE.ok(r)

@app.route('/quota', methods=['GET'])
def quota():
  username = request.args.get('username')

  try:
    r = monitor.query_quota(username)
    if r: return RESPONSE.ok(r)
    else: return RESPONSE.fail(f'username {username!r} not found')
  except Exception as e:
    logger.error(format_exc())
    return RESPONSE.fail(f'server internal error: {e}')

@app.route('/realloc', methods=['POST'])
def realloc():
  try:
    data = request.json
    username = b64decode(data.get('username').encode()).decode()
    password = b64decode(data.get('password').encode()).decode()
    gpu_count = int(data.get('gpu_count'))
    assert None not in [username, password, gpu_count]
  except:
    logger.error(f'postdata: {data}')
    return RESPONSE.fail('parameter wrong')
  
  try: 
    r = monitor.alloc_gpu(username, password, gpu_count)
    return type(r) == str and RESPONSE.fail(r) or RESPONSE.ok(r)
  except Exception as e:
    logger.error(format_exc())
    return RESPONSE.fail(f'server internal error: {e}')


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
