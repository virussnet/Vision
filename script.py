import time
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import webbrowser
from PIL import Image, ImageTk, ImageSequence
import pystray
import sys
import os
import win32api
import win32con
import win32gui
import win32ts


def resource_path(relative_path):
    """ Получение абсолютного пути для ресурсов """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def configure_styles():
    """ Настройка стилей интерфейса """
    style = ttk.Style()
    style.theme_use('clam')
    style.configure('TFrame', background='#ffffff')
    style.configure('TLabel', background='#ffffff', foreground='#2d3436', font=('Arial', 11))
    style.configure('Main.TButton',
                    font=('Arial', 11, 'bold'),
                    width=35,
                    padding=10,
                    background='#74b9ff',
                    foreground='white',
                    borderwidth=0)
    style.map('Main.TButton',
              background=[('active', '#0984e3')],
              foreground=[('active', 'white')])
    style.configure('TEntry',
                    font=('Arial', 11),
                    padding=8,
                    bordercolor='#74b9ff',
                    lightcolor='#74b9ff',
                    fieldbackground='#f8f9fa')


class SessionMonitor:
    """ Мониторинг системных событий """

    def __init__(self):
        self.hWnd = win32gui.CreateWindowEx(0, "STATIC", "SessionMonitor", 0, 0, 0, 0, 0, 0, 0, 0, None)
        win32ts.WTSRegisterSessionNotification(self.hWnd, win32ts.NOTIFY_FOR_THIS_SESSION)

    def start(self):
        win32gui.PumpMessages()


class MainWindow:
    """ Главное окно программы """

    def __init__(self):
        self.root = tk.Tk()
        self.cat_frames = []
        self.last_short = time.time()
        self.last_long = time.time()
        self.setup_window()
        self.load_assets()
        self.create_widgets()
        self.setup_tray()
        self.start_session_monitor()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_window(self):
        """ Инициализация окна """
        self.root.title("Защита зрения | GroupSchumacher")
        self.root.geometry("370x360")
        self.root.resizable(False, False)
        configure_styles()
        self.center_window(self.root)
        try:
            self.root.iconbitmap(ICON_PATH)
        except Exception:
            pass

    def center_window(self, window):
        """ Центрирование окна """
        window.update_idletasks()
        width = window.winfo_width()
        height = window.winfo_height()
        x = (window.winfo_screenwidth() // 2) - (width // 2)
        y = (window.winfo_screenheight() // 2) - (height // 2)
        window.geometry(f'+{x}+{y}')

    def load_assets(self):
        """ Загрузка анимации """
        try:
            gif = Image.open(GIF_PATH)
            for img in ImageSequence.Iterator(gif):
                resized = img.copy().resize((220, 220))
                self.cat_frames.append(ImageTk.PhotoImage(resized))
        except Exception as e:
            print(f"Ошибка загрузки анимации: {e}")

    def create_widgets(self):
        """ Создание элементов интерфейса """
        main_frame = ttk.Frame(self.root)
        main_frame.pack(pady=20, padx=25, fill='both', expand=True)

        buttons = [
            ("▶ Запустить таймер", self.start_timer),
            ("⏸ Приостановить", self.toggle_pause),
            ("⚡ Тест короткого перерыва", lambda: self.show_break("short")),
            ("🔋 Тест длинного перерыва", lambda: self.show_break("long")),
            ("⚙ Настройки", lambda: SettingsWindow(self)),
            ("ℹ О программе", lambda: AboutWindow(self))
        ]

        for text, cmd in buttons:
            btn = ttk.Button(main_frame, text=text, style='Main.TButton', command=cmd)
            btn.pack(pady=6)

    def start_timer(self):
        """ Запуск основного цикла """
        threading.Thread(target=self.main_loop, daemon=True).start()

    def toggle_pause(self):
        """ Переключение паузы """
        global paused
        paused = not paused
        self.update_tray_menu()

    def show_break(self, break_type):
        """ Отображение окна перерыва """
        global active_break
        active_break = True
        duration = short_break_duration if break_type == "short" else long_break_duration
        BreakWindow(self, break_type, duration)
        active_break = False

    def setup_tray(self):
        """ Настройка системного трея """
        try:
            image = Image.open(ICON_PATH)
        except FileNotFoundError:
            image = Image.new('RGB', (64, 64), color='white')

        menu = pystray.Menu(
            pystray.MenuItem('Открыть', lambda: self.root.deiconify()),
            pystray.MenuItem('Приостановить', self.toggle_pause),
            pystray.MenuItem('Выход', self.quit_program)
        )
        self.tray_icon = pystray.Icon("tray_icon", image, "Защита зрения", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def start_session_monitor(self):
        """ Запуск мониторинга сессии """
        self.session_monitor = SessionMonitor()
        threading.Thread(target=self.session_monitor.start, daemon=True).start()

    def update_tray_menu(self):
        """ Обновление меню трея """
        if self.tray_icon: self.tray_icon.update_menu()

    def quit_program(self):
        """ Полное закрытие программы """
        global running
        running = False
        self.root.destroy()
        if self.tray_icon: self.tray_icon.stop()

    def on_closing(self):
        """ Сворачивание в трей вместо закрытия """
        self.root.withdraw()
        if self.tray_icon: self.tray_icon.visible = True

    def main_loop(self):
        """ Основной рабочий цикл """
        global running, paused, active_break, system_locked
        pause_start_time = 0

        while running:
            if not paused and not active_break and not system_locked:
                now = time.time()

                # Корректировка времени при разблокировке
                if system_locked and pause_start_time == 0:
                    pause_start_time = now
                elif not system_locked and pause_start_time > 0:
                    pause_duration = now - pause_start_time
                    self.last_long += pause_duration
                    self.last_short += pause_duration
                    pause_start_time = 0

                # Проверка перерывов
                if (now - self.last_long >= long_break_interval and
                        (now - self.last_short >= MIN_BREAK_GAP)):
                    self.show_break("long")
                    self.last_long = self.last_short = time.time()

                elif (now - self.last_short >= short_break_interval and
                      (now - self.last_long >= MIN_BREAK_GAP)):
                    self.show_break("short")
                    self.last_short = time.time()

                time.sleep(1)
            else:
                time.sleep(0.5)


class BreakWindow:
    """ Окно перерыва """

    def __init__(self, main_app, break_type, duration):
        self.main_app = main_app
        self.break_type = break_type
        self.duration = duration
        self.cat_frames = main_app.cat_frames

        self.setup_window()
        self.create_content()
        self.main_app.root.wait_window(self.window)

    def setup_window(self):
        """ Инициализация окна """
        self.dim_window = tk.Toplevel(self.main_app.root)
        self.dim_window.attributes("-fullscreen", True)
        self.dim_window.attributes("-alpha", 0.93)
        self.dim_window.configure(bg="#2d3436")
        self.dim_window.attributes("-topmost", True)

        self.window = tk.Toplevel(self.main_app.root)
        self.window.title("Сделай перерыв -))")
        self.window.geometry("400x530")
        self.window.resizable(False, False)
        self.window.attributes("-topmost", True)
        self.center_window(self.window)
        self.window.grab_set()
        self.window.focus_force()
        self.window.protocol("WM_DELETE_WINDOW", self.close)

    def create_content(self):
        """ Создание содержимого окна """
        main_frame = ttk.Frame(self.window)
        main_frame.pack(pady=25, padx=30, fill='both', expand=True)

        # Заголовок
        title = "Короткий перерыв!" if self.break_type == "short" else "Длинный перерыв!"
        ttk.Label(main_frame, text=title, font=('Arial', 14, 'bold')).pack(pady=15)

        # Анимация
        if self.cat_frames:
            self.animation_label = ttk.Label(main_frame)
            self.animation_label.pack()
            self.animate(0)

        # Инструкция
        message = ("Поморгайте глазами 10 раз!\nРасслабьте мышцы лица."
                   if self.break_type == "short" else
                   "1. Посмотрите вдаль\n2. Сделайте вращения глазами\n3. Закройте глаза на 5 сек")
        ttk.Label(main_frame, text=message, justify='center').pack(pady=15)

        # Таймер
        self.time_label = ttk.Label(main_frame, text=f"Осталось: {self.duration} сек", font=('Arial', 12, 'bold'))
        self.time_label.pack(pady=15)

        # Кнопка
        ttk.Button(main_frame, text="Пропустить", style='Main.TButton', command=self.close).pack(pady=10)
        self.update_timer()

    def animate(self, frame_idx):
        """ Анимация кота """
        if hasattr(self, 'animation_label') and self.animation_label.winfo_exists():
            self.animation_label.configure(image=self.cat_frames[frame_idx])
            self.window.after(1000, self.animate, (frame_idx + 1) % len(self.cat_frames))

    def update_timer(self):
        """ Обновление таймера """
        if self.duration > 0 and self.window.winfo_exists():
            self.duration -= 1
            self.time_label.config(text=f"Осталось: {self.duration} сек")
            self.window.after(1000, self.update_timer)
        else:
            self.close()

    def close(self):
        """ Закрытие окна """
        global active_break
        active_break = False

        # Сброс таймеров
        if self.break_type == "short":
            self.main_app.last_short = time.time()
        else:
            self.main_app.last_long = time.time()

        if self.dim_window.winfo_exists(): self.dim_window.destroy()
        if self.window.winfo_exists(): self.window.destroy()

    def center_window(self, window):
        """ Центрирование окна """
        window.update_idletasks()
        width = window.winfo_width()
        height = window.winfo_height()
        x = (window.winfo_screenwidth() // 2) - (width // 2)
        y = (window.winfo_screenheight() // 2) - (height // 2)
        window.geometry(f'+{x}+{y}')


class SettingsWindow:
    """ Окно настроек """

    def __init__(self, main_app):
        self.main_app = main_app
        self.window = tk.Toplevel(self.main_app.root)
        self.setup_window()
        self.create_widgets()

    def setup_window(self):
        self.window.title("Настройки")
        self.window.geometry("400x400")
        self.window.resizable(False, False)
        self.main_app.center_window(self.window)

    def create_widgets(self):
        main_frame = ttk.Frame(self.window)
        main_frame.pack(pady=25, padx=30, fill='both', expand=True)

        ttk.Label(main_frame, text="Настройка интервалов", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        fields = [
            ("Короткие перерывы (мин):", short_break_interval // 60),
            ("Длинные перерывы (мин):", long_break_interval // 60),
            ("Длит. короткого (сек):", short_break_duration),
            ("Длит. длинного (мин):", long_break_duration // 60)
        ]

        self.entries = []
        for text, value in fields:
            frame = ttk.Frame(main_frame)
            frame.pack(pady=8, fill='x')
            ttk.Label(frame, text=text).pack(side='left')
            entry = ttk.Entry(frame, width=8, style='TEntry')
            entry.insert(0, str(value))
            entry.pack(side='right')
            self.entries.append(entry)

        ttk.Button(main_frame, text="Сохранить настройки", style='Main.TButton', command=self.save_settings).pack(
            pady=20)

    def save_settings(self):
        global short_break_interval, long_break_interval, short_break_duration, long_break_duration
        try:
            short_break_interval = int(self.entries[0].get()) * 60
            long_break_interval = int(self.entries[1].get()) * 60
            short_break_duration = int(self.entries[2].get())
            long_break_duration = int(self.entries[3].get()) * 60
            messagebox.showinfo("Успех", "Настройки успешно сохранены!")
            self.window.destroy()
        except ValueError:
            messagebox.showerror("Ошибка", "Некорректные значения!")


class AboutWindow:
    """ Окно 'О программе' """

    def __init__(self, main_app):
        self.main_app = main_app
        self.window = tk.Toplevel(self.main_app.root)
        self.setup_window()
        self.create_widgets()

    def setup_window(self):
        self.window.title("О программе")
        self.window.geometry("360x280")
        self.window.resizable(False, False)
        self.main_app.center_window(self.window)

    def create_widgets(self):
        main_frame = ttk.Frame(self.window)
        main_frame.pack(pady=25, padx=30, fill='both', expand=True)

        text = """Разработчик: Лях Виталий Николаевич
Программист 1С | ООО "Шумахер"

Зрение - наш главный инструмент. 
Регулярные перерывы помогают:
- Снизить усталость глаз
- Предотвратить синдром сухого глаза
- Сохранить остроту зрения"""

        ttk.Label(main_frame, text=text, justify='left').pack(pady=10)
        ttk.Button(main_frame, text="Связаться с разработчиком", style='Main.TButton',
                   command=lambda: webbrowser.open("https://t.me/vitalyliakh")).pack(pady=15)


# ===== Глобальные настройки =====
ICON_PATH = resource_path("icon.ico")
GIF_PATH = resource_path("cat.gif")
short_break_interval = 10 * 60  # 10 минут
long_break_interval = 50 * 60  # 50 минут
short_break_duration = 8  # 8 секунд
long_break_duration = 5 * 60  # 5 минут
running = True
paused = False
active_break = False
system_locked = False
MIN_BREAK_GAP = 60  # 1 минута

if __name__ == "__main__":
    app = MainWindow()
    app.root.mainloop()