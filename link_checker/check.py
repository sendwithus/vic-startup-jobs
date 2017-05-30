from gevent import monkey
monkey.patch_all()

import re
import sys

import requests
from gevent.pool import Pool


markdown_page = 'https://raw.githubusercontent.com/sendwithus/vic-startup-jobs/master/README.md'
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
            response = requests.get(link, headers=self.headers, allow_redirects=True, stream=True)

            # print status and URL info for links resulting in non-OK responses
            # so we can clean up the jobs listing
            if response.status_code >= 400:
                try:
                    domain = re.match(r'https?://([^/]+)/', link).groups()[0]
                except:
                    domain = '--no domain match--'
                print('-', response.status_code, domain, text, link)
                self.bad_links.append((response.status_code, domain, text, link))
            else:
                valid = True
        except requests.exceptions.InvalidSchema as e:
            # ignore mailto: link errors, but print anything else, as it's
            # likely incorrect URL formatting in the markdown
            if not link.startswith('mailto:'):
                print('Error fetching URL, invalid URL schema:', e, file=sys.stderr)
                self.bad_links.append(('Invalid schema', link))
        except Exception as e:
            # something else happened, print to diagnose
            print('Error testing URL:', link, text, 'Exception:', e, file=sys.stderr)
            self.bad_links.append(('Error: {}'.format(e), link))
        finally:
            if response:
                response.close()

        self.already_seen.append(link)

    def parse_page(self, page):
        response = requests.get(page, headers=self.headers, allow_redirects=True)
        if response.ok:
            links = re.findall(r'\[([^\]]+)\]\(([^\)]+)\)', response.text)

            pool = Pool(100)
            pool.map(self.check_link, links)
            pool.join()

            print('Done checking {} URLs'.format(len(links)))
        else:
            print('Could not retrieve job listings page.')

        if self.bad_links:
            print('\n-- Bad Links --')
            for link_info in self.bad_links:
                print(*link_info)
            return False

        return True


if __name__ == '__main__':
    if not LinkChecker().parse_page(markdown_page):
        sys.exit(1)
