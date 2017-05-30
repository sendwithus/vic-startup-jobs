Overview
--------

A Python script to quickly 'test' the URLs in the jobs listing.

Run in Docker
-------------
```
docker run -it -v "${PWD}/link_checker":/usr/src -w /usr/src python:3.6 /bin/sh -c "pip install -r requirements.txt && python check.py"
```

Notes
-----

* doesn't catch pages that have been 'removed' but return a 200 status code or redirect to a healthy page.
