import hashlib
import os
import sys
import tarfile
import zipfile
import requests
import os.path as osp

from urllib.request import urlopen
from urllib.parse import urlparse


class Downloader:
    MB = 1024*1024
    BUFSIZE = 10*MB

    def __init__(self, **kwargs):
        self._name = kwargs.pop('name')
        self._url = kwargs.pop('url', None)
        self._filename = kwargs.pop('filename')
        self._sha = kwargs.pop('sha', None)
        self._saveTo = kwargs.pop('saveTo', './data')
        self._extractTo = kwargs.pop('extractTo', './data')

    def __str__(self):
        return 'Downloader for <{}>'.format(self._name)

    def printRequest(self, r):
        def getMB(r):
            d = dict(r.info())
            for c in ['content-length', 'Content-Length']:
                if c in d:
                    return int(d[c]) / self.MB
            return '<unknown>'
        print('    {} {} [{} Mb]'.format(r.getcode(), r.msg, getMB(r)))

    def verifyHash(self):
        if not self._sha:
            return False
        sha = hashlib.sha1()
        try:
            with open(osp.join(self._saveTo, self._filename), 'rb') as f:
                while True:
                    buf = f.read(self.BUFSIZE)
                    if not buf:
                        break
                    sha.update(buf)
            if self._sha != sha.hexdigest():
                print('    actual {}'.format(sha.hexdigest()))
                print('    expect {}'.format(self._sha))
            return self._sha == sha.hexdigest()
        except Exception as e:
            print('    catch {}'.format(e))

    def get(self):
        print('  {}: {}'.format(self._name, self._filename))
        if self.verifyHash():
            print('    hash match - skipping download')
        else:
            basedir = os.path.dirname(self._saveTo)
            if basedir and not os.path.exists(basedir):
                print('    creating directory: ' + basedir)
                os.makedirs(basedir, exist_ok=True)

            print('    hash check failed - downloading')
            if 'drive.google.com' in self._url:
                urlquery = urlparse(self._url).query.split('&')
                for q in urlquery:
                    if 'id=' in q:
                        gid = q[3:]
                sz = GDrive(gid)(osp.join(self._saveTo, self._filename))
                print('    size = %.2f Mb' % (sz / (1024.0 * 1024)))
            else:
                print('    get {}'.format(self._url))
                self.download()

            # Verify hash after download
            print('    done')
            print('    file {}'.format(self._filename))
            if self.verifyHash():
                print('    hash match - extracting')
            else:
                print('    hash check failed - exiting')

        # Extract
        if '.zip' in self._filename:
            print('    extracting - ', end='')
            self.extract()
            print('done')

        return True

    def download(self):
        try:
            r = urlopen(self._url, timeout=60)
            self.printRequest(r)
            self.save(r)
        except Exception as e:
            print('  catch {}'.format(e))

    def extract(self):
        fileLocation = os.path.join(self._saveTo, self._filename)
        try:
            if self._filename.endswith('.zip'):
                with zipfile.ZipFile(fileLocation) as f:
                    for member in f.namelist():
                        path = osp.join(self._extractTo, member)
                        if osp.exists(path) or osp.isfile(path):
                            continue
                        else:
                            f.extract(member, self._extractTo)
        except Exception as e:
            print(('  catch {}'.format(e)))

    def save(self, r):
        with open(self._filename, 'wb') as f:
            print('  progress ', end='')
            sys.stdout.flush()
            while True:
                buf = r.read(self.BUFSIZE)
                if not buf:
                    break
                f.write(buf)
                print('>', end='')
                sys.stdout.flush()


def GDrive(gid):
    def download_gdrive(dst):
        session = requests.Session()  # re-use cookies

        URL = "https://docs.google.com/uc?export=download"
        response = session.get(URL, params = { 'id' : gid }, stream = True)

        def get_confirm_token(response):  # in case of large files
            for key, value in response.cookies.items():
                if key.startswith('download_warning'):
                    return value
            return None
        token = get_confirm_token(response)

        if token:
            params = { 'id' : gid, 'confirm' : token }
            response = session.get(URL, params = params, stream = True)

        BUFSIZE = 1024 * 1024
        PROGRESS_SIZE = 10 * 1024 * 1024

        sz = 0
        progress_sz = PROGRESS_SIZE
        with open(dst, "wb") as f:
            for chunk in response.iter_content(BUFSIZE):
                if not chunk:
                    continue  # keep-alive

                f.write(chunk)
                sz += len(chunk)
                if sz >= progress_sz:
                    progress_sz += PROGRESS_SIZE
                    print('>', end='')
                    sys.stdout.flush()
        print('')
        return sz
    return download_gdrive

# Data will be downloaded and extracted to ./data by default
data_downloaders = dict(
    face=Downloader(name='face',
        url='https://drive.google.com/u/0/uc?id=1lOAliAIeOv4olM65YDzE55kn6XjiX2l6&export=download',
        sha='8397f115c0d4447e55ea05488579e71a813e2691',
        filename='face.zip'),
    text=Downloader(name='text',
        url='https://drive.google.com/u/0/uc?id=1lTQdZUau7ujHBqp0P6M1kccnnJgO-dRj&export=download',
        sha='a40cf095ceb77159ddd2a5902f3b4329696dd866',
        filename='text.zip'),
)

if __name__ == '__main__':
    selected_data_names = []
    for i in range(1, len(sys.argv)):
        selected_data_names.append(sys.argv[i])
    if not selected_data_names:
        selected_data_names = list(data_downloaders.keys())
    print('Data will be downloaded: {}'.format(str(selected_data_names)))

    download_failed = []
    for selected_data_name in selected_data_names:
        downloader = data_downloaders[selected_data_name]
        if not downloader.get():
            download_failed.append(downloader._name)

    if download_failed:
        print('Data have not been downloaded: {}'.format(str(download_failed)))