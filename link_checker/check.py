from gevent import monkey
monkey.patch_all()

import re
import sys

import requests
from gevent.pool import Pool


markdown_file = 'README.md'
user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'


class LinkChecker(object):
    bad_links = []
    maybe_bad_links = []
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
            response = requests.get(link, headers=self.headers, allow_redirects=True, stream=True)

            try:
                domain = re.match(r'https?://([^/]+)/', link).groups()[0]
            except:
                domain = '--no domain match--'

            # print status and URL info for links resulting in non-OK responses
            # so we can clean up the jobs listing
            if response.status_code >= 400:
                self.bad_links.append((response.status_code, domain, text, link))
            elif response.history and response.history[0].status_code in (301, 302):
                self.maybe_bad_links.append((response.status_code, domain, text, link))
        except requests.exceptions.MissingSchema:
            # in-page anchor links will trigger this error
            pass
        except requests.exceptions.InvalidSchema as e:
            # ignore mailto: link errors, but print anything else, as it's
            # likely incorrect URL formatting in the markdown
            if not link.startswith('mailto:'):
                self.bad_links.append(('Invalid schema', link))
        except Exception as e:
            # something else happened, print to diagnose
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

        print('Done checking {} URLs'.format(len(links)))

        if self.maybe_bad_links:
            print('\n-- Redirects that MIGHT BE Bad Links --')
            for link_info in self.maybe_bad_links:
                print(*link_info)

        if self.bad_links:
            print('\n-- Bad Links --')
            for link_info in self.bad_links:
                print(*link_info)
            return False

        return True


if __name__ == '__main__':
    if not LinkChecker().parse_page(markdown_file):
        sys.exit(1)
