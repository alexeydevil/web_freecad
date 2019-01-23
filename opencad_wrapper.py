#!/usr/bin/python
# -*- coding: utf-8 -*-

# built-in
import os
from PIL import Image
from pyvirtualdisplay.smartdisplay import SmartDisplay

# service
from OCC.Display.SimpleGui import init_display

from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox


def export_to_image(path_to_cad_file, width=1280, height=1024, result_format=".jpg"):
    """
    Метод формирует по исходному файлу 
    изображение с заданным расширением
    """

    # Проверяем что переданный путь существует
    if not os.path.isfile(path_to_cad_file) or \
       not os.access(path_to_cad_file, os.R_OK):
           return None

    # Получаем имя файла
    result_file_name = path_to_cad_file.split('.')[0] + result_format

    # Запускаем виртуальный дисплей, на котором будем формировать gui
    with SmartDisplay(visible=0, size=(width, height), bgcolor='black') as disp:
        # Формируем площадку для отображения данных используя OpenCAD
        display, start_display, add_menu, add_function_to_menu = init_display("wx", size=(width, height))

        # Вычитываем переданный файл с расширением .stp
        step_reader = STEPControl_Reader()
        step_reader.ReadFile(path_to_cad_file)
        step_reader.TransferRoot()
        shape = step_reader.Shape()

        # Отображаем полученную фигуру
        display.DisplayShape(shape, update=True)
        
        # Снимаем дамп с экрана
        display.View.Dump(result_file_name)
 
	# К сожалению, при работе через xvfb код выше 
        # сохраняет данные только в формате bitmap, 
        # из-за этого приходиться преобразовывать изображения вручную
        im = Image.open(result_file_name)
        im.save(result_file_name)

    return result_file_name
