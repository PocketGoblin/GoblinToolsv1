import json
from pathlib import Path
from tkinter import filedialog


IMAGE_FILETYPES = [('Image Files', '*.png;*.jpg;*.jpeg'), ('All Files', '*.*')]


def ask_image_file(title='Open Image'):
    return filedialog.askopenfilename(title=title, filetypes=IMAGE_FILETYPES)


def ask_directory(title='Select Export Folder'):
    return filedialog.askdirectory(title=title)


def write_json_file(path, payload):
    Path(path).write_text(json.dumps(payload, indent=2), encoding='utf-8')


def write_hex_lines(path, hex_values):
    Path(path).write_text('\n'.join(hex_values) + '\n', encoding='utf-8')
