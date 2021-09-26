# sodayo-mini (便乗)

    For your measly laboratory GPUs usage quota managing.
    Write tm a hammer write, just do a dam single script implementation of `sodayo`! :(

----

## Quickstart

  - web
    - follow `web/README.md`
  - server
    - rename `quota_init.txt-skel` to `quota_init.txt`, setup your quota rules
    - rename `settings.py-skel` to `settings.py`, make your setting
    - run server `python3 sodayo.py`
    - point your browser according to `SERVER_SOCKET`
  - cmdline client
    - run `python3 sdy.py --quota <@all|@me|username>` query quota remnants
    - run `python3 sdy.py --realloc 3` try reallocating `3` GPUs


#### requirements

  - flask & flask-cors
  - gpustat
  - paramiko

----
Armit, 2021/9/23
