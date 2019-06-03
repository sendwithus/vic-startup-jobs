import random

from gevent import monkey
monkey.patch_all()

import re
import sys
import traceback
import warnings

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

blacklist = [
    "https://www.juul.ca"
]

class LinkChecker(object):
    bad_links = []
    already_seen = []

    def check_link(self, args):
        text, link = args

        if link in self.already_seen:
            return
        
        if link in blacklist:
            return

        headers = {
            'user-agent': random.choice(user_agents)
        }

        response = None
        try:
            response = requests.get(link, headers=headers, allow_redirects=True, verify=False, timeout=30)

            # collect status and URL info for links resulting in non-OK responses
            # so we can clean up the jobs listing
            if response.status_code >= 400:
                try:
                    domain = re.match(r'https?://([^/]+)/', link).groups()[0]
                except:
                    domain = '--no domain match--'
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
            # something else happened, print to diagnose, but also continue processing links
            print("-" * 60)
            traceback.print_exc(file=sys.stderr)
            print("-" * 60)
            self.bad_links.append(('Error: {}'.format(e), link))
        finally:
            if response:
                response.close()

        self.already_seen.append(link)

    def parse_page(self, md_file):
        raw_markdown = open(md_file, 'r').read()
        links = re.findall(r'\[([^\]]+)\]\(([^\)]+)\)', raw_markdown)

        pool = Pool(100)
        pool.map(self.check_link, links)
        pool.join()

        result = True
        if self.bad_links:
            print('\n-- Bad Links --')
            for link_info in self.bad_links:
                print(*link_info)
            result = False

        print('\nDone checking {} URLs.'.format(len(links)))

        return result


if __name__ == '__main__':
    if not LinkChecker().parse_page(markdown_file):
        sys.exit(1)
