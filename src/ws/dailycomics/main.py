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
        if 'agent' in comic:
            http.headers['user-agent'] = comic['agent']
        r = http.get(comic['url'])
        if 'url_change' in comic:
            url = _extract(r.text, comic['url_change'])
            r = http.get(url)
        comic['img_url'] = _extract(r.text, comic['pattern'])
        if 'base' in comic:
            comic['img_url'] = comic['base'] + comic['img_url']
        _download_image(http, comic)
        if 'alt' in comic:
            comic['alt'] = _extract(r.text, comic['alt'])
    return comic


def _download_image(http, comic):
    r = http.get(comic['img_url'], stream=True)
    filename = urlparse(comic['img_url']).path
    _, ext = os.path.splitext(os.path.basename(filename))
    comic['image'] = f'{comic["id"]}-{TODAY_STR}{ext}'
    with open(comic['image'], 'wb') as f:
        for chunk in r.iter_content(2048):
            f.write(chunk)


def _extract(text, pattern):
    result = re.search(pattern, text, re.DOTALL)
    return result.group(1) if result else None
