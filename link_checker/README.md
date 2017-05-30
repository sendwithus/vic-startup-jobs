Overview
--------

A Python script to quickly 'test' the URLs in the jobs listing.

Setup
-----

Assuming you've checked out the latest code and using `virtualenvwrapper` based toolset (but easily adapted for plain `virtualenv`):
```
cd link_checker
mkvirtualenv -p python3 vsj-checker
setvirtualenvproject
pip install -r requirements.txt
```

Usage
-----

After installation, run it and look for non-200 status code output. Should be mostly 404s.
```
workon vsj-checker
python3 check.py
```

Notes
-----

* doesn't catch pages that have been 'removed' but return a 200 status code or redirect to a healthy page.
