#!/usr/bin/python
# -*- coding: utf-8 -*-

# built-in
import os
import sys
import argparse
from PIL import Image
from pyvirtualdisplay import Display

# service
from OCC.Display.SimpleGui import init_display

from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox


def export_to_image(params):
    """
    Метод формирует по исходному файлу 
    изображение с заданным расширением
    """

    # Проверяем что переданный путь существует
    if not os.path.isfile(params.get("path_to_cad")) or \
       not os.access(params.get("path_to_cad"), os.R_OK):
           raise RuntimeError

    screen_size = (int(params.get("width")), int(params.get("height")))

    # Запускаем виртуальный дисплей, на котором будем формировать gui
    xvfb_display = Display(visible=0, size=screen_size, bgcolor='black')
    xvfb_display.start()

    # Формируем площадку для отображения данных используя OpenCAD
    #display, _, _, _ = init_display("wx", size=(width, height))
    display, _, _, _ = init_display("wx", size=screen_size)

    # Вычитываем переданный файл с расширением .stp
    step_reader = STEPControl_Reader()
    step_reader.ReadFile(params.get("path_to_cad"))
    step_reader.TransferRoot()
    shape = step_reader.Shape()

    # Отображаем полученную фигуру
    display.DisplayShape(shape, update=True)
    
    # Снимаем дамп с экрана
    display.View.Dump(params.get("path_to_image"))

    # К сожалению, при работе через xvfb код выше 
    # сохраняет данные только в формате bitmap, 
    # из-за этого приходиться преобразовывать изображения вручную
    img = Image.open(params.get("path_to_image"))
    img.save(params.get("path_to_image"))
    
    xvfb_display.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--path_to_cad')
    parser.add_argument('-i', '--path_to_image')
    parser.add_argument('-w', '--width', default=1280)
    parser.add_argument('-o', '--height', default=1024)
    parser.add_argument('-s', '--scale', default=1)
    args = parser.parse_args()

    export_to_image(vars(parser.parse_args()))