Overview
=========

A bash script to quickly 'test' the URLs in the jobs listing.

The only dependencies are at least cURL version 6.5.1 and bash version 4. This means it's really likely that you don't have to do anything special to run this script, it probably already works on your system. 

Usage
=========

You can simply run
```sh
link_checker/check.sh README.md 
```
and be on your way. Although, there's lots of other ways to use the link checker. Fundamentally, it can check the validity of links in any markdown document - but only those using the `[]()` link style. External reference - e.g. those `[][]` coupled with `[]: link` - and html style `<a href=''>` aren't implemented here.

A docker based approach is possible too, but finding a trusted image with both bash and cURL installed is difficult. If you'd like to run in docker, use the official bash image and install `curl`.

```sh
docker run -it --rm -v $PWD:/mnt bash -c 'apk add curl; /mnt/link_checker/check.sh /mnt/README.md'
```

Return codes
---------

The return code will represent the total number of potential issues flagged - if 2 links don't resolve and another 5 links 404, the return code will be 7. This doesn't exactly follow standard POSIX return code paradigms, but should be good for our use cases - zero still represents success with no errors.

If a line in the log mentioned something about a **CURLcode**, it's referring to the error codes of cURL itself. The complete list can be found in [cURL's documentation](https://curl.haxx.se/libcurl/c/libcurl-errors.html). These errors are related to the link being checked, not this script.

Modes
---------

This script has two output modes, both can be used concurrently. 

1. The first is the default, it logs things for your eyeballs to see. It can be disabled with the `--quiet` flag. These messages are sent via standard error, so redirecting them requires redirecting file descriptor 2.

1. The second is opt-in, and it produces a bulleted list of checkboxes in markdown. You can use it in the MR to quickly show us which things you changed. Use the `--markdown` flag to enable this. The lines of your markdown list are sent via standard output (file descriptor 1), so redirection works as normal. 

Workers
----------
By default, the link checker will work on checking 4 links at a time. This allows us to carry on a little bit if one link is taking a long time to respond. The `--workers` flag controls the number of workers to use. With about 200 links to check, 10 workers can get through them pretty quickly.

Complex usage
----------
This example does lots at once! The current published version of the job-board is pulled from github, links are discovered, 10 workers go through links in a queue to check their status, log messages are written to the terminal, and a markdown file listing the seemingly fufulled links is written to a file so you can examine it later, and even use it in your merge request description! 

[![asciicast](https://asciinema.org/a/mO5NNWDH5EJkxYIzvgy5ht1h5.svg)](https://asciinema.org/a/mO5NNWDH5EJkxYIzvgy5ht1h5)

Notes
-----

* Doesn't catch pages that have been 'removed' but return a 2xx status code or redirect to a healthy page.
* Can produce false positive for hyper-vigilant, overzealous servers
