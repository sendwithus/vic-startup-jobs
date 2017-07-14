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
user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'


class LinkChecker(object):
    bad_links = []
    already_seen = []
    headers = {
        'user-agent': user_agent
    }

    def check_link(self, args):
        text, link = args

        if link in self.already_seen:
            return

        response = None
        try:
            response = requests.get(link, headers=self.headers, allow_redirects=True, stream=True, verify=False)

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
