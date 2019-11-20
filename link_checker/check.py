from gevent import monkey
monkey.patch_all()

import itertools
import random
import re
import sys
import traceback
import warnings

import gevent
from gevent.pool import Pool
import requests
from urllib3.exceptions import InsecureRequestWarning

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

markdown_file = 'README.md'

user_agents = [
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:54.0) Gecko/20100101 Firefox/54.0",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:18.0) Gecko/20100101 Firefox/18.0",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36 Edge/16.16299"
]

class LinkChecker(object):
    bad_links = []
    assumed_good_links = []
    links_already_seen = []
    domains_already_seen = []

    def check_link(self, args):
        text, link = args

        if link in self.links_already_seen:
            return

        headers = {
            'User-Agent': random.choice(user_agents)
        }

        try:
            domain = re.match(r'https?://([^/]+)/', link).groups()[0].lower()
        except:
            return

        if domain in self.domains_already_seen:
            # slow down requests for domains we've already seen
            gevent.sleep(1)
        else:
            self.domains_already_seen.append(domain)

        response = None
        try:
            response = requests.get(link, headers=headers, allow_redirects=True, verify=False, timeout=30)
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            # collect status and URL info for links resulting in non-OK responses
            # so we can clean up the jobs listing
            self.bad_links.append((response.status_code, domain, text, link))
        except requests.exceptions.MissingSchema:
            # in-page anchor links will trigger this error
            pass
        except requests.exceptions.InvalidSchema as e:
            # ignore mailto: link errors, but print anything else, as it's
            # likely incorrect URL formatting in the markdown
            if not link.startswith('mailto:'):
                print('Error fetching URL, invalid URL schema:', e, file=sys.stderr)
                self.bad_links.append(('Invalid schema', link))
        except Exception as e:
            if isinstance(e, requests.exceptions.ConnectionError) and 'RemoteDisconnected' in str(e):
                # let's just assume that remote disconnections are from hyper-vigilant, overzealous
                # servers - and that the links are still good (unfortunately).
                self.assumed_good_links.append(('Remote server disconnected', link))
            else:
                # something else happened, print to diagnose, but also continue processing links
                print("-" * 60)
                traceback.print_exc(file=sys.stderr)
                print("-" * 60)
                self.bad_links.append(('Error: {}'.format(e), link))
        finally:
            if response:
                response.close()

        self.links_already_seen.append(link)

    def parse_page(self, md_file):
        raw_markdown = open(md_file, 'r', encoding="utf8").read()
        links = re.findall(r'\[([^\]]+)\]\(([^\)]+)\)', raw_markdown)
        # randomize to help avoid sequential requests to the same server
        random.shuffle(links)

        pool = Pool(5)
        pool.map(self.check_link, links)
        pool.join()

        if self.bad_links or self.assumed_good_links:
            print('\n-- Bad Links --')
            for link_info in itertools.chain(self.bad_links, self.assumed_good_links):
                print(*link_info)

        print('\nDone checking {} URLs.'.format(len(links)))

        # only use self.bad_links to determine if the link check failed; we _know_ those are
        # actual bad links that we KNOW we can fix/remove
        return bool(self.bad_links)


if __name__ == '__main__':
    if LinkChecker().parse_page(markdown_file):
        sys.exit(1)
