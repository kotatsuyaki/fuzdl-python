from typing import List
from os import environ
from pathlib import Path
from dataclasses import dataclass
import base64

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.firefox.options import Options


@dataclass
class Chapter:
    title: str
    elem: WebElement


BLOB_SCRIPT = """
    var uri = arguments[0];
    var callback = arguments[1];
    var toBase64 = function(buffer){for(var r,n=new Uint8Array(buffer),t=n.length,a=new Uint8Array(4*Math.ceil(t/3)),i=new Uint8Array(64),o=0,c=0;64>c;++c)i[c]="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/".charCodeAt(c);for(c=0;t-t%3>c;c+=3,o+=4)r=n[c]<<16|n[c+1]<<8|n[c+2],a[o]=i[r>>18],a[o+1]=i[r>>12&63],a[o+2]=i[r>>6&63],a[o+3]=i[63&r];return t%3===1?(r=n[t-1],a[o]=i[r>>2],a[o+1]=i[r<<4&63],a[o+2]=61,a[o+3]=61):t%3===2&&(r=(n[t-2]<<8)+n[t-1],a[o]=i[r>>10],a[o+1]=i[r>>4&63],a[o+2]=i[r<<2&63],a[o+3]=61),new TextDecoder("ascii").decode(a)};
    var xhr = new XMLHttpRequest();
    xhr.responseType = 'arraybuffer';
    xhr.onload = function(){ callback(toBase64(xhr.response)) };
    xhr.onerror = function(){ callback(xhr.status) };
    xhr.open('GET', uri);
    xhr.send();
"""


class App:
    def __init__(self) -> None:
        options = Options()
        options.headless = True
        self.driver = webdriver.Firefox(options=options)
        self.driver.set_window_size(960, 1080)
        # Implicitly wait 10 seconds for finding *any* element
        # See https://www.selenium.dev/documentation/webdriver/waits/
        self.driver.implicitly_wait(10)
        self.series_title = ''

    def close(self) -> None:
        self.driver.close()

    def login(self, email: str, password: str) -> None:
        print('Login')

        self.driver.get('https://comic-fuz.com/account/signin')

        email_elem, password_elem = self.find_signin_inputs()
        login_elem = self.find_by_class_prefix('signin_form__button')

        email_elem.send_keys(email)
        password_elem.send_keys(password)
        login_elem.click()

        print('Waiting for login success')

        # Wait for login success element to appear
        success_elem = self.find_by_class_prefix('signin_signin__description')
        assert success_elem.text == 'ログインが完了しました。'

    def download_series(self, series_url: str):
        self.driver.get(series_url)

        # Get metadata of the series
        print('Waiting for metadata')

        title_elem = self.find_by_class_prefix(
            'title_detail_introduction__name')
        self.series_title = title_elem.text

        # Find chapter elements and convert to `Chapter` objects
        free_chapters = self.get_free_chapters()
        num_free_chapters = len(free_chapters)

        # Download every chapter that is "free"
        print('Downloading chapters')

        for i in range(0, num_free_chapters):
            chapter = free_chapters[i]
            print(f'Download chapter {chapter.title}')
            self.download_chapter(chapter)

            # Refresh free_chapters, since the elements are dead
            free_chapters = self.get_free_chapters()
            assert num_free_chapters == len(free_chapters)

    def get_free_chapters(self) -> List[Chapter]:
        chapter_elems = self.find_chapters()
        chapters: List[Chapter] = []
        for el in chapter_elems:
            title_elem = self.find_by_class_prefix(
                'Chapter_chapter__name', root=el)
            is_free = '無料' in el.text

            # Skip non-free chapters
            if not is_free:
                continue

            chapters.append(Chapter(
                title=title_elem.text,
                elem=el,
            ))
        return chapters

    def download_chapter(self, chapter: Chapter):
        print('Opening viewer')
        chapter.elem.click()

        page_elem = self.find_by_class_prefix('ViewerFooter_footer__page')
        # The word after "/" is total number
        num_pages = int(page_elem.text.split('/')[1])
        print(f'{chapter.title} has {num_pages} pages')

        # Ensure the directory
        dir = Path(self.series_title).joinpath(chapter.title)
        dir.mkdir(parents=True, exist_ok=True)

        # the -1 accounts for the last page, not part of manga
        for p in range(0, num_pages - 1):
            img_elem = self.find(f'img[alt=page_{p}]')

            # Wait until img src becomes not-None
            WebDriverWait(self.driver, timeout=10).until(
                lambda _: img_elem.get_attribute('src') is not None)
            img_src = img_elem.get_attribute('src')

            print(f'Downloading page {p} blob {img_src}')
            img_bytes = self.fetch_blob_img(img_src)
            self.save_file(dir, p, img_bytes)

            # Turn page
            self.find('body').send_keys(Keys.ARROW_LEFT)

        self.driver.back()

    def fetch_blob_img(self, uri: str) -> bytes:
        result = self.driver.execute_async_script(BLOB_SCRIPT, uri)
        if type(result) == int:
            raise Exception("Request failed with status %s" % result)
        return base64.b64decode(result)

    def save_file(self, dir: Path, page: int, data: bytes):
        """Save file to """
        dest = dir.joinpath(f'{page:03}.png')
        with open(dest, 'wb') as f:
            f.write(data)

    # Purpose-specific find methods

    def find_signin_inputs(self) -> List[WebElement]:
        return self.find_all(f'[class^=signin_form__input]')

    def find_chapters(self) -> List[WebElement]:
        return self.find_all('ul>[class^=Chapter_chapter]')

    # Utilities for all the find_* methods above.
    def find(self, selector: str, root=None) -> WebElement:
        if root is None:
            return self.driver.find_element(By.CSS_SELECTOR, selector)
        else:
            return root.find_element(By.CSS_SELECTOR, selector)

    def find_all(self, selector: str, root=None) -> List[WebElement]:
        if root is None:
            return self.driver.find_elements(By.CSS_SELECTOR, selector)
        else:
            return root.find_elements(By.CSS_SELECTOR, selector)

    def find_by_class_prefix(self, prefix: str, root=None) -> WebElement:
        return self.find(f'[class^={prefix}]', root=root)


def main():
    email = environ['EMAIL']
    password = environ['PASSWORD']
    series_url = environ['SERIES_URL']

    # Create /tmp directory (for Docker environment)
    try:
        Path('/tmp').mkdir(parents=True,exist_ok=True)
    except Exception as e:
        pass

    app = App()
    try:
        app.login(email, password)
        app.download_series(series_url)
    except Exception as e:
        print('Exception:', e)
    finally:
        input('Enter to close browser')
        app.close()


if __name__ == '__main__':
    main()
