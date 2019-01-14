#!/usr/bin/python
# -*- coding: utf-8 -*-

import json              # для формирования корректного ответа
import time              # для работы с таймаутами
import uuid              # генерация уникального идентификатора задания
import queue             # работа с threadsafe очередью
import base64            # строка может быть и в base64 формате
import threading         # работа с мультипоточностью
from aiohttp import web  # основной модуль на asyncio для работы с запросами и т.д.


routes = web.RouteTableDef()

HOST = "localhost"
PORT = 3332

THREAD_COUNT = 10         # Максимальное количество одновременно работающих потоков
MAX_TASK_IN_QUEUE = 1000  # Максимальное количество задач в очереди


EXT_FORMAT = ".png"   # Формат сохраняемого изображения
DEFAULT_WIDTH = 1280  # Ширина результирующего изображения
DEFAULT_HEIGHT = 1024 # Высота результирующего изображения 
DEFAULT_SCALE = 1     # Коэффициэнт сжатия изображения по диагонали

MAX_CONTENT_SIZE = 1024**2*100 # Максимальный размер входного контента

# Словарь с набором результирующих состояний
RESPONSE_INFO = {
    "failed_to_execute" : {"info":"Runtime error", "code":400},
    "in_processing" : {"info":"The task is in progress", "code":204},
    "bad_parameters" : {"info":"Incorrect parameters", "code":400},
    "is_ok" : {"info":"Success", "code" : 200},
}


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

        # Генерируем уникальное имя для задачи
        self.setName(uuid.uuid4())

        # Стартуем поток
        self.start()


    def execute(self, task):
        """
        Выполняет посталенную задачу
        и формирует конечный результат в виде готовой картинки.
        После чего помещает в результирующий набор либо путь
        до картинки, либо информацию об ошибке
        """
        
        result_list[threading.get_ident()] = {
                "item_guid" : self.getName(),
                "status" : 200,
                "path" : "/tmp/test.png"
            }


    def run(self):
        """
        Запускаем задачу, которая мониторит очередь задач
        и выполняет задачи находящиеся в ней
        """

        # переменная, отображающая состояние работы основного кода потока
        state='free'
        
        # метод run() циклически выполняется до тех пор, пока атрибуту экземпляра класса need_exists не будет присвоено значение True
        while not self.need_exit:
            try:
                # получаем задание из очереди, причем не используем блокировку и устанавливаем таймаут 1 секунда.
                # Это означает, что если в течениеи 1 секунды все запросы на получение задания из очереди провалятся,
                # то будет сгенерировано исключение Queue.Empty, указывающее, что очередь пуста.
                task=self.__queue.get(block=False, timeout=1)
                self.execute(task)

                # Если было получено задание из очереди, то меняется статус работы на busy
                state='busy'
            except queue.Empty:
                # Меняем статус работы на free
                state='free'
                # засыпаем на долю секунды, что бы не загружать процессор
                time.sleep(0.1)


class Task(threading.Thread):
    """
    В данном классе помещаем задачу в очередь.
    Если очередь переполнена, то пытаемся дождаться
    свободного лота. В случае перегруженности кидаем
    сообвествующую ошибку.
    """

    def __init__(self, task_queue, new_task):
        super(Task, self).__init__()

        self.__queue = task_queue
        self.__task = new_task

        self.setDaemon(True)
        self.start()

    def execute(self):

        # Переменная, отображающая состояние очереди
        state='full'

        while True:
            try:
                # Помещаем задание в очередь, при этом не используем блокировку и устанавливаем таймаут операции в 1 сек.
                # Это означает, что если в течение 1 секунды все попытки поместить задание в очередь окажутся неудачными,
                # то будет сгенерировано исключение Queue.Full, указывающее что очередь переполнена.
                self.__queue.put(self.__task, block=False, timeout=1)
                
                # Если предыдущая операция завершилась успешно,то меняем состояние работы на 'avaiable'
                state='available'

                # Делаем небольшой перерыв между отправкой следующего задания в очередь
                time.sleep(1)
                # Выходим из цикла while и переходим на следующую итерацию цикла for
                break
            except queue.Full:
                # Чтобы не засорять вывод ненужной информацией выводим состояние очереди только после его смены
                if state!='full':
                    print(u'Queue is full, in queue %s'%','.join(map(str,self.__queue.__dict__['queue'])))
                # Меняем состояние очереди на full
                state='full'
                # Делаем задержку перед очередной попыткой отправить задание в очередь
                time.sleep(1)


@routes.post('/stp2png')
async def post_request(request):
    """
    Метод обрабатывает все POST
    запросы к сервису
    """

    # Получаем исходный файл
    data = await request.read()
    
    # Проверяем что полученный файл формата STEP
    if data[:13] != "ISO-10303-21;".encode("utf-8"):
        # Попробуем расскодировать из base64 данную строку
        try:
            data = base64.b64decode(data).decode('utf-8')
        except:
            pass
        # Ну и еще раз проверим
        if data[:13] != "ISO-10303-21;".encode("utf-8"):
            print("Check format")
            raise web.HTTPBadRequest
    
    # Формируем итоговую задачу
    task = {
        "data" : data,
        "width" : request.rel_url.query.get('width') or DEFAULT_WIDTH,
        "height" : request.rel_url.query.get('height') or DEFAULT_HEIGHT,
        "scale" : request.rel_url.query.get('scale') or DEFAULT_SCALE,
    }

    Task(task_queue, task).execute()
    raise web.HTTPOk


@routes.get('/stp2png')
async def get_request(request):
    """
    Метод обрабатывает все GET 
    запросы к сервису
    """
    
    # Получаем идентификатор задачи, 
    # у которой требуется узнать результат
    item_id = request.rel_url.query.get('item_id')

    # Если в запросе нет подобного идентификатора,
    # то ругаемся и уходим
    if item_id is None:
        raise web.HTTPBadRequest

    # Если задачи с указанным идентификатором нет,
    # то ругаемся и уходим
    if not result_list.get(item_id):
        raise web.HTTPFound

    # Проверяем текущий статус задачи
    if result_list[item_id]["status"] != "is_ok":
        # Если процесс уже завершился, то удаляем его из списка
        if not result_list[item_id]["status"] == "in_processing":
            result_list.pop(item_id, None)

        # Сообщаем пользователю о проблеме
        return web.json_response(
            dumps=json.dumps,
            content_type='application/json',
            body=RESPONSE_INFO[result_list[item_id]["status"]]["info"],
            status=RESPONSE_INFO[result_list[item_id]["status"]]["code"], 
        )

    # Пытаемся получить сформированный результат
    result_data = None
    with open(result_list[item_id]["path"]) as result_file:
        result_data = result_file.read()

    # Если результирующий файл все же пуст,
    # то сообщаем об этом и удаляем задачу из списка
    if not result_data:
        raise web.HTTPExpectationFailed

    # Если проблем нет, то получаем картинку 
    # и отдаем в качестве результата
    return web.json_response(
        result_data,
        status=RESPONSE_INFO[result_list[item_id]["status"]]["code"], 
        content_type='application/json',
        dumps=json.dumps
    )


# Создаем очередь с заданной длиной 2, это означает что одновременно в очереди могут находиться не более 2ух заданий
task_queue = queue.Queue(MAX_TASK_IN_QUEUE)
result_list = {}

# Создаем набор потоков обслуживающих очередь
workers=[Worker(task_queue) for x in range(THREAD_COUNT)]

# Запускаем веб приложение для обслуживания пославленных задач
app = web.Application(client_max_size=MAX_CONTENT_SIZE)
app.add_routes(routes)
web.run_app(app, host=HOST, port=PORT)
