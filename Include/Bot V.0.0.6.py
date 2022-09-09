import vk_api
import random
import time
import threading

import requests
import mysql.connector as sql

from Lib.Sql_executor import executor
from vk_api.longpoll import VkLongPoll, VkEventType
from bs4 import BeautifulSoup as bs
from multiprocessing import Process, Event




class MangaNoficationBot(VkLongPoll):

    def __init__(self):

        print("Бот создан")
        # API вк

        self.token = 'Token'
        self.vk = vk_api.VkApi(token=self.token)
        self.longpoll = VkLongPoll(self.vk)
        # DataBase

        # Session
        self.headers = {'accept': '*/*',
                        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36'}
        self.session = requests.Session()

        # основная ссылка для поиска манги

        self.search_mintmanga_url = 'http://mintmanga.live/search/advanced?s_completed=ex&s_single=ex&q='
        self.mintmanga_url = 'http://mintmanga.live'

        self.search_readmanga_url = 'readmanga.live/search/advanced?s_completed=ex&s_single=ex&q='
        self.readmanga_url = 'readmanga.live'

    # функция отправки сообщений вк
    def write_msg(self, user_id, message):
        # без random_id не работает
        self.vk.method('messages.send', {'user_id': user_id,
                                         'message': message,
                                         'random_id': random.randrange(100000, 999999)})

    # сам бот
    def bot_script(self):
        # слушаем канал сообщений
        try:
            for event in self.longpoll.listen():

                # если новое сообщение
                if event.type == VkEventType.MESSAGE_NEW:
                    # если для бота
                    if event.to_me:
                        self.sql_executor = executor.Sql_executor(event.user_id)

                        # добываем данные из БД и добавляем их в список

                        in_choice_manga = self.sql_executor.select('vk_id', 'in_choice_manga')
                        in_choice_title = self.sql_executor.select('vk_id', 'in_choice_title')
                        in_option = self.sql_executor.select('vk_id', 'in_option')

                        print("in_option = ", in_option, "\n")
                        print("in_choice_manga = ", in_choice_manga, "\n")
                        print("in_choice_title = ", in_choice_title, "\n")
                        print("User_write ", event.text, "\n")

                        self.main_choice = event.text
                        # если выбор 1

                        if event.user_id in in_choice_manga:

                            # передача переменной значения названия манги
                            self.manga = event.text

                            if self.find_manga(event.user_id) == "Манга не найденна":
                                self.write_msg(event.user_id, "Манга не найденна")
                                self.main_menu(event.user_id)

                                self.sql_executor.delete('in_choice_manga')
                                self.sql_executor.add(str(event.user_id), 'in_option')
                                continue

                            send_manga = self.create_manga_msg()
                            # отправка сообщения с номером, названием и сылкой на мангу

                            self.write_msg(event.user_id, send_manga)

                            # переводит словарь найденной манги для дальнейшого переобразования обратно в словарь
                            manga_dict = str(self.manga_track_dict.copy())

                            self.write_msg(event.user_id, "Какую мангу вы хотите отслеживать?")

                            self.sql_executor.delete('in_choice_manga')
                            add_dict = str(event.user_id) + ', ' + '"{}"'.format(manga_dict)
                            self.sql_executor.add(add_dict, 'in_choice_title')

                        if event.user_id in in_option:

                            # показать в конос  ле что написал человек который написал боту
                            if self.main_choice == "1":
                                self.write_msg(event.user_id, "Какую мангу вы хотите найти?")

                                self.sql_executor.add(str(event.user_id), 'in_choice_manga')
                                self.sql_executor.delete('in_option')
                            else:
                                self.write_msg(event.user_id, "Ошибка ввода")

                        if event.user_id in in_choice_title:

                            manga_track = self.sql_executor.select('manga_dict', 'in_choice_title',
                                                                   ' where vk_id = {}'.format(str(event.user_id)))

                            # выбор пользователя есть в словаре
                            title_is_int = True

                            for i in manga_track:

                                manga_track_str = eval(i)
                                title = manga_track_str.get(str(event.text))

                                if title == None:
                                    self.write_msg(event.user_id, "Необходимо выбрать число")
                                    title_is_int = False
                                    break

                            if title_is_int == True:

                                manga_request = mn.session.get(title, headers=mn.headers)
                                manga_soup = bs(manga_request.content, 'lxml')
                                current_chapter = manga_soup.find(name='h4')
                                chapter = current_chapter.text
                                try:
                                    chapter = chapter.replace('Читать', '')
                                    chapter = chapter.replace(' ', '')
                                    chapter = chapter.replace('новое', '')

                                    print(current_chapter)
                                except:
                                    print("Cannot replace chapter name")

                                self.sql_executor.add(
                                    "'{title}', '{chapter}', '{user_id}'".format(title=title, chapter=chapter,
                                                                                 user_id=str(event.user_id)),
                                    'tracked_manga')

                                self.write_msg(event.user_id, "Манга успешно добавлена в отслеживаемое")
                                self.sql_executor.delete('in_choice_title')
                                self.sql_executor.add(str(event.user_id), 'in_option')
                                self.main_menu(event.user_id)
                            else:
                                continue

                        if event.user_id not in in_option and event.user_id not in in_choice_manga and event.user_id not in in_choice_title:
                            self.main_menu(event.user_id)
                            self.sql_executor.add(str(event.user_id), 'in_option')
        except:
            pass

    def find_manga(self, user_id):
        # создание словаря в котором содержатся отдельно ссылка и называние наёденной манги
        # нужно что бы потом заносить в БД

        # словарь в котором ссылка и название вместе(нужно для отправки в вк)
        self.manga_track_dict = {}
        self.manga_track = {}
        # что бы из относительной ссылки сделать абсолютную

        # мангу которую нужно искать
        q = self.manga
        self.max_elements = 5

        # готовая ссылка на результат поиска
        finded_manga_list_readmanga = self.manga_site(self.search_readmanga_url)
        finded_manga_list_mintmanga = self.manga_site(self.search_mintmanga_url)

        if len(finded_manga_list_mintmanga) == 0 and len(finded_manga_list_readmanga) == 0:
            CANT_FIND_MANGA = "Манга не найденна"
            print(CANT_FIND_MANGA)
            return CANT_FIND_MANGA

        t1 = threading.Thread(target=self.create_full_href,
                              args=(finded_manga_list_readmanga, self.readmanga_url, user_id))
        t2 = threading.Thread(target=self.create_full_href,
                              args=(finded_manga_list_mintmanga, self.mintmanga_url, user_id))
        t1.start()
        t2.start()

    def manga_from_each_site(self):
        """ собирает по 5 тайтлов с каждого сайта """
        # готовая ссылка на результат поиска
        finded_manga_list = self.manga_site(self.search_mintmanga_url)

        if len(finded_manga_list) == 0:
            print("EMPTY_MANGA_LIST")

            finded_manga_list = self.manga_site(self.search_readmanga_url)
            if len(finded_manga_list) == 0:
                ERROR = "Манга не найденна"
                print(ERROR)
                return ERROR

    def create_full_href(self, manga_list, manga_url, user_id):
        """ цикл создания полной ссылки для каждой манги  """

        manga_number = 1
        for manga in manga_list:

            try:
                manga_title = manga.text
                manga_title = manga_title.replace("\n", "")
                manga_href = manga.find('a')['href']

                # проверка на относительную ссылку
                if manga_href[0] == '/':
                    full_manga_href = manga_url + manga_href
                    manga_title_and_href = manga_title + " " + full_manga_href

                    # добавление найденной манги в словарь
                    if manga_number <= self.max_elements:
                        self.manga_track.update({str(manga_number): manga_title_and_href})
                        self.manga_track_dict.update({str(manga_number): full_manga_href})
                        manga_number += 1

                    else:
                        break
                else:
                    print("Connection Failed")

            except Exception as e:
                print(e)
                pass

    def main_menu(self, user_id):
        """ Главноее меню бота """
        text = """
            1 - Добавить мангу 
                   """

        self.write_msg(user_id, text)

    def create_manga_msg(self):
        send_manga = ""
        # отправка сообщения с номером, названием и сылкой на мангу
        print(self.manga_track)
        for key, val in self.manga_track.items():
            send_manga = send_manga + key + ": " + str(val) + "\n\n"
            print(val)
        return send_manga

    def manga_site(self, site):
        """ в site ставить searchurl """
        finded_manga_url = site + self.manga
        finded_manga_url = finded_manga_url.replace(" ", "%20")

        request_for_site = self.session.get(finded_manga_url, headers=self.headers)
        soup_for_site = bs(request_for_site.content, 'lxml')

        print(finded_manga_url)
        print("soup created")
        print("REQUSEST CODE is " + str(request_for_site.status_code))

        if request_for_site.status_code == 200:
            finded_manga_list = soup_for_site.find_all(name='h3')

            return finded_manga_list
        else:
            raise Exception("Cannot connect to ", finded_manga_url)


mn = MangaNoficationBot()


class UpadateManga:
    def __init__(self):
        self.sql_executor = executor.Sql_executor()

    def update(self):
        while True:
            print('Updating...')
            tracked_urls = self.sql_executor.select('manga_url', 'tracked_manga')
            new_chapter_dict = {}

            for url in tracked_urls:

                manga_request = mn.session.get(url, headers=mn.headers)
                manga_soup = bs(manga_request.content, 'lxml')
                current_chapter = manga_soup.find(name='h4')

                try:
                    current_chapter = self.delete_extra_words(current_chapter)
                except Exception:
                    print("Can't delete extra words")

                print(current_chapter)
                execute_str = ' where manga_url = "{}"'.format(url)

                previous_chapter = self.sql_executor.select('last_chapter', 'tracked_manga', execute_str)
                previous_chapter_str = ''.join(previous_chapter)
                print(previous_chapter_str)

                if previous_chapter_str != current_chapter:
                    self.sql_executor.execute(
                        "Update tracked_manga set last_chapter = '{chapter}' where manga_url = '{url}';".format(
                            chapter=current_chapter, url=url))

                    vk_id = self.sql_executor.select('vk_id', 'tracked_manga', ' where manga_url = "{}"'.format(url))

                    manga_name = manga_soup.find('span', {'class': 'name'})
                    vk_id = "".join(vk_id)
                    new_chapter_dict.update({vk_id: {manga_name.text: url}})

            if len(new_chapter_dict):
                self.send_new_chapter_msg(vk_id, new_chapter_dict)
            time.sleep(5)

    def send_new_chapter_msg(self, user_id, dict):
        for vk_id, manga in dict.items():
            for manga_name, url in manga.items():
                text = """Вышла новая глава манги {manga_name}
                            {url}""".format(manga_name=manga_name, url=url)
                mn.write_msg(vk_id, text)
        print('Msg sended for ' + vk_id)

    def delete_extra_words(self, word):
        word = word.text
        try:
            word = word.replace(' ', '')
        except:
            print("Can'not replace ' '")

        try:
            word = word.replace('Читать', '')
        except:
            print("Can'not replace Читать")

        try:
            word = word.replace('новое', '')
        except:
            pass

        return word


um = UpadateManga()
update = um.update
bott = mn.bot_script
proc = []
bot = threading.Thread(target=mn.bot_script)
upadter = threading.Thread(target=um.update)
print(123)

if __name__ == '__main__':
    upadter.start()
    print("updater start")
    bot.start()

    print(1233333)
