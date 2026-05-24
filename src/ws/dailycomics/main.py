from markupsafe import Markup
from urllib.parse import urlparse
from yaml import safe_load as yaml_load
import argparse
import datetime
import jinja2
import os
import re
import requests
import traceback


TODAY = datetime.datetime.today()
TODAY_STR = TODAY.strftime('%Y-%m-%d')
HERE = os.path.dirname(__file__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--folder', default=os.getcwd())
    parser.add_argument('--template', default=HERE + '/template.html')
    options = parser.parse_args()

    os.chdir(options.folder)

    with open(options.config) as f:
        config = yaml_load(f)
    comics = []
    for comic in config['comics']:
        comic['id'] = comic['title'].lower().replace(' ', '')
        try:
            comics.append(download(comic))
        except RuntimeError as e:
            comic['alt'] = Markup(f'<b>Status {e.args[0]}</b>')
            comics.append(comic)
        except Exception as e:
            comic['alt'] = Markup('<pre>' + '\n'.join(traceback.format_exception(e)) + '</pre>')
            comics.append(comic)

    with open(options.template) as f:
        template = jinja2.Template(f.read())
    result = template.render({
        'comics': comics,
        'date': TODAY,
        'day': datetime.timedelta(days=1),
    })
    with open(f'dailystrips-{TODAY_STR}.html', 'w') as f:
        f.write(result)


def download(comic):
    with requests.Session() as http:
        if 'headers' in comic:
            http.headers.update(comic['headers'])
        r = http.get(comic['url'])
        if not r.ok:
            raise RuntimeError(r.status_code)
        if 'url_change' in comic:
            url = _extract(r.text, comic['url_change'])
            r = http.get(url)
        if 'alt' in comic:
            comic['alt'] = _extract(r.text, comic['alt'])
        comic['images'] = []
        for i, url in enumerate(re.findall(comic['pattern'], r.text)):
            comic['images'].append(_download_image(http, comic, url, i))
            if not comic.get('pattern_multi'):
                break
    return comic


def _download_image(http, comic, url, index):
    if 'base' in comic:
        url = comic['base'] + url

    r = http.get(url, stream=True)
    if not r.ok:
        raise RuntimeError(r.status_code)
    filename = urlparse(url).path
    _, ext = os.path.splitext(os.path.basename(filename))
    filename = f'{comic["id"]}-{TODAY_STR}-{index}{ext}'
    with open(filename, 'wb') as f:
        for chunk in r.iter_content(2048):
            f.write(chunk)
    return filename


def _extract(text, pattern):
    result = re.search(pattern, text, re.DOTALL)
    return result.group(1) if result else None
