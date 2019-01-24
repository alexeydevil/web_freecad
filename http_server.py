#!/usr/bin/python
# -*- coding: utf-8 -*-

# built-in
import os                # модуль для работы с файловой системой ОС
import json              # для формирования корректного ответа
import time              # для работы с таймаутами
import uuid              # генерация уникального идентификатора задания
import sched             # модуль простого планировщика
import queue             # работа с threadsafe очередью
import shlex             # Лексиграфический разбор параметров
import base64            # строка может быть и в base64 формате
import fnmatch           # разбор пути до файла
import datetime          # модуль для работы с датами
import threading         # работа с мультипоточностью
import subprocess        # работа с подпроцессами
from aiohttp import web  # основной модуль на asyncio для работы с запросами и т.д.

# service
import simple_scheduler


routes = web.RouteTableDef()

PORT = int(os.getenv("MAIN_PORT") or 3345)

TIMEOUT = int(os.getenv("TIMEOUT_FOR_CONVERT") or 30)

TEMP_FOLDER = "/tmp/"

ENTER_EXT = ".stp"
RESULT_EXT = ".png"

TEMP_PATH_STP = TEMP_FOLDER + "share_{}" + ENTER_EXT
TEMP_PATH_IMAGE = TEMP_FOLDER + "share_{}" + RESULT_EXT

THREAD_COUNT = int(os.getenv("MAX_COUNT_THREAD") or 10)  # Максимальное количество одновременно работающих потоков
MAX_TASK_IN_QUEUE = int(os.getenv("MAX_TASKS") or 1000)   # Максимальное количество задач в очереди

DEFAULT_WIDTH = int(os.getenv("DEFAULT_WIDTH") or 1280)
DEFAULT_HEIGHT = int(os.getenv("DEFAULT_HEIGHT") or 1024)
DEFAULT_SCALE = 1  # Коэффициэнт сжатия изображения по диагонали

MAX_CONTENT_SIZE = 1024**2*100 # Максимальный размер входного контента

# Словарь с набором результирующих состояний
RESPONSE_INFO = {
    "failed_to_execute" : {"info":"Runtime error", "code" : 400},
    "in_processing" : {"info":"The task is in progress", "code" : 202},
    "bad_parameters" : {"info":"Incorrect parameters", "code" : 400},
    "is_ok" : {"info":"Success", "code" : 200},
}


@simple_scheduler.async
@simple_scheduler.schedule(600)
def cleaner():
    """
    Метод удаляет все исходные и результирующие 
    файлы созданных больше чем 10 часов назад
    """

    def delete_files(folder, pattern, hours=10):
        """
        Метод удаляем из указанной папки все 
        возможные файлы которые попадают под 
        паттерн и старше указанного количества часов
        """

        for root, _, files in os.walk(folder):
            for filename in fnmatch.filter(files, pattern):
                path = root + '/' + filename

                if not os.path.isfile(path) or \
                not os.access(path, os.R_OK):
                    continue
                
                timestamp_from_file = datetime.datetime.fromtimestamp(os.path.getmtime(path))
                if (datetime.datetime.now() - timestamp_from_file) > datetime.timedelta(hours=hours):
                    os.remove(path)

    # Удаляем исходные файлы
    delete_files(TEMP_FOLDER, "*" + ENTER_EXT)
    
    # Удаляем результирующие файлы
    delete_files(TEMP_FOLDER, "*" + RESULT_EXT)

class Worker(threading.Thread):
    """
    Класс, обслуживающий задачи из очереди.
    """

    def __init__(self, task_queue):
        super(Worker, self).__init__()

        self.__queue=task_queue

        # Переменная, указывающая о 
        # необходимости завершения работы потока
        self.need_exit=False

        # Все сторонние задачи запускаем 
        # в режиме отсоединенных потоков
        self.setDaemon(True)

        # Стартуем поток
        self.start()

    def execute(self, task):
        """
        Выполняет посталенную задачу
        и формирует конечный результат в виде готовой картинки.
        После чего помещает в результирующий набор либо путь
        до картинки, либо информацию об ошибке
        """

        def export_to_image(path_to_cad, path_to_image, width, height, scale):
            """
            Не трогать этот метод.
            Он в отдельном процессе под отдельной сессией 
            запускает gui opencad для 
            формирования итогового изображения
            """

            try:
                command = "python3 opencad_wrapper.py --path_to_cad {} --path_to_image {} --width {} --height {} --scale {}".format(
                    path_to_cad,
                    path_to_image,
                    width,
                    height,
                    scale
                )
                proc = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                _, _ = proc.communicate(timeout=TIMEOUT)
            except subprocess.TimeoutExpired:
                proc.kill()
                _, _ = proc.communicate()

        # Получаем картинку по исходному файлу
        try:
            export_to_image(
                task.get("path_to_cad"),
                task.get("path_to_image"),
                task.get("width"),
                task.get("height"),
                task.get("scale"),
            )
        except:
            result_list[task.get("id")] = {
                "status" : RESPONSE_INFO["failed_to_execute"],
                "start_time" : result_list[task.get("id")]["start_time"],
                "end_time" : datetime.datetime.now()
            }
            return

        result_list[task.get("id")] = {
            "status" : RESPONSE_INFO["is_ok"],
            "path" : task.get("path_to_image"),
            "start_time" : result_list[task.get("id")]["start_time"],
            "end_time" : datetime.datetime.now()
        }

    def run(self):
        """
        Запускаем задачу, которая мониторит очередь задач
        и выполняет задачи находящиеся в ней
        """
        
        # метод run() циклически выполняется до тех пор, пока атрибуту экземпляра класса need_exists не будет присвоено значение True
        while not self.need_exit:
            try:
                # получаем задание из очереди, причем не используем блокировку и устанавливаем таймаут 1 секунда.
                # Это означает, что если в течениеи 1 секунды все запросы на получение задания из очереди провалятся,
                # то будет сгенерировано исключение Queue.Empty, указывающее, что очередь пуста.
                task = self.__queue.get(block=False, timeout=1)
                self.execute(task)
            except queue.Empty:
                # засыпаем на долю секунды, что бы не загружать процессор
                time.sleep(0.1)


class Task(threading.Thread):
    """
    В данном классе помещаем задачу в очередь.
    Если очередь переполнена, то пытаемся дождаться
    свободного лота. В случае перегруженности кидаем
    сообвествующую ошибку.
    """

    def __init__(self, task_queue):
        super(Task, self).__init__()

        self.__queue = task_queue
        self.__id = uuid.uuid4().hex
        self.setDaemon(True)
        self.start()

    def id(self):
        return self.__id

    def execute(self, new_task):
        """
        Метод помещает задачу в общую очередь задач
        """
        
        # Сразу обозначаем в результирующем 
        # списке что задача у нас есть
        # и обозначаем временем дату ее начала
        result_list[self.id()] = {
            "status" : RESPONSE_INFO["in_processing"],
            "start_time" : datetime.datetime.now()
        }
        new_task["id"]=self.id()

        while True:
            try:
                # Помещаем задание в очередь, при этом не используем блокировку и устанавливаем таймаут операции в 1 сек.
                # Это означает, что если в течение 1 секунды все попытки поместить задание в очередь окажутся неудачными,
                # то будет сгенерировано исключение Queue.Full, указывающее что очередь переполнена.
                self.__queue.put(new_task, block=False, timeout=1)
                # Выходим из цикла while и переходим на следующую итерацию цикла for
                break
            except queue.Full:                
                # Делаем задержку перед очередной попыткой отправить задание в очередь
                time.sleep(1)


@routes.post('/stp2png')
async def post_request(request):
    """
    Метод обрабатывает все POST
    запросы к сервису
    """

    def check_format_signature(binary_data):
        """
        Метод проверяет тип 
        получаемого файла по его сигнатуре
        """

        # Проверяем что полученный файл формата STEP
        if binary_data[:13] == "ISO-10303-21;".encode("utf-8"):
            return binary_data

        # Попробуем расскодировать из base64 данную строку
        try:
            binary_data = base64.b64decode(binary_data).decode('utf-8')
            # Ну и еще раз проверим
            if binary_data[:13] == "ISO-10303-21;".encode("utf-8"):
                return binary_data
        except:
            pass

        raise web.HTTPBadRequest

    def save_post_data(task_id, binary_data):
        """
        Метод сохраняет полученный бинарный 
        файл на диск и возвращает путь до него
        """

        temp_path = TEMP_PATH_STP.format(task_id)
        with open(temp_path ,"wb") as file_path:
            file_path.write(binary_data)
        return temp_path

    # Получаем данные из post запроса
    binary_file = await request.read()

    # Проверяем сигнатуру данных
    binary_file = check_format_signature(binary_file)

    # Формируем итоговую задачу
    current_task = Task(task_queue)
    params = {
        "path_to_cad" : save_post_data(current_task.id(), binary_file),
        "path_to_image" : TEMP_PATH_IMAGE.format(current_task.id()),
        "width" : request.rel_url.query.get('width') or DEFAULT_WIDTH,
        "height" : request.rel_url.query.get('height') or DEFAULT_HEIGHT,
        "scale" : request.rel_url.query.get('scale') or DEFAULT_SCALE,
    }

    # Запускаем задачу на выполнение
    current_task.execute(params)

    # Говорим что все хорошо и 
    # возвращаем идентификатор задачи
    return web.json_response(
        dumps=json.dumps,
        content_type='application/json',
        body=current_task.id(),
        status=RESPONSE_INFO["in_processing"]["code"]
    )


@routes.get('/stp2png')
async def get_request(request):
    """
    Метод обрабатывает все GET 
    запросы к сервису
    """

    def get_response(task_id):
        """
        Формируем ответ и удаляем временные данные
        """

        # Пытаемся получить сформированный результат
        result_data = None
        with open(result_list[task_id]["path"], 'rb') as result_file:
            result_data = result_file.read()

        # Как только все необходимые данные получены, 
        # то удаляем все созданные временные 
        # файлы вместе с задачей из очереди
        result_list.pop(task_id, None)
        os.remove(TEMP_PATH_STP.format(task_id))
        os.remove(TEMP_PATH_IMAGE.format(task_id))

        # Если результирующий файл все же пуст,
        # то сообщаем об этом
        if not result_data:
            raise web.HTTPExpectationFailed

        return base64.b64encode(result_data).decode("utf-8")

    # Получаем идентификатор задачи, 
    # у которой требуется узнать результат
    task_id = request.rel_url.query.get('item_id')

    # Если в запросе нет подобного идентификатора,
    # то ругаемся и уходим
    if task_id is None:
        raise web.HTTPBadRequest

    # Если задачи с указанным идентификатором нет,
    # то ругаемся и уходим
    if not result_list.get(task_id):
        raise web.HTTPNoContent

    # Проверяем текущий статус задачи
    if result_list[task_id]["status"]["code"] != RESPONSE_INFO["is_ok"]["code"]:
        # Если процесс уже завершился, то удаляем его из списка
        if not result_list[task_id]["status"] != RESPONSE_INFO["in_processing"]["code"]:
            result_list.pop(task_id, None)

        # Сообщаем пользователю о проблеме
        return web.json_response(
            dumps=json.dumps,
            content_type='application/json',
            body=RESPONSE_INFO[result_list[task_id]["status"]]["info"],
            status=RESPONSE_INFO[result_list[task_id]["status"]]["code"], 
        )

    # Если проблем нет, то получаем картинку 
    # и отдаем в качестве результата
    return web.json_response(
        get_response(task_id),
        status=RESPONSE_INFO["is_ok"]["code"], 
        content_type='application/json',
        dumps=json.dumps
    )


# Создаем очередь с заданной длиной
task_queue = queue.Queue(MAX_TASK_IN_QUEUE)
result_list = {}

# Создаем набор потоков обслуживающих очередь
workers=[Worker(task_queue) for x in range(THREAD_COUNT)]

# Запускаем задачу по очистке временных файлов
cleaner()

# Запускаем веб приложение для обслуживания пославленных задач
app = web.Application(client_max_size=MAX_CONTENT_SIZE)
app.add_routes(routes)
web.run_app(app, port=PORT)
