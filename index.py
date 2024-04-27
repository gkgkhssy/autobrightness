import pystray, cv2, time

from threading import Thread
from queue import Empty, Queue
from tkinter import Text, Tk, ttk
from pystray import MenuItem, Menu
from PIL import Image

import public

settings_open = False  # 判断设置页面是否已打开
settings_updata = False  # 判断设置是否更新


# 挂载任务
def background_task(q):
    # 初始化
    public.initialize("config.ini")

    # 创建VideoCapture对象，参数0表示使用默认的摄像头
    cap = cv2.VideoCapture(public.SETTING["CAMERA"])

    # 检查可用摄像头
    if not cap.isOpened():
        print("Error opening video stream or file")
        foo = 0
        while 1:
            cap = cv2.VideoCapture(foo)
            if cap.isOpened():
                print(f"Your available cameras is:{foo}")
                public.SETTING["CAMERA"] = foo
                break
            elif foo < 5:
                foo += 1
            else:
                print("You don't have a camera ")
                return

    bri_old = -1  # 上一次亮度记录值
    bri_now = -1  # 现在的屏幕亮度
    bri_recom = -100  # 推荐的屏幕亮度
    bri_stable = 0  # 稳定计数器

    # 逐帧捕获
    while True:
        # 设置更新退出循环
        if settings_updata:
            cap.release()
            cv2.destroyAllWindows()
            return

        ret, frame = cap.read()
        if not ret:
            foo = 0
            # 睡眠唤醒超时计时
            while foo < 30:
                time.sleep(1)
                foo += 1
                cap.release()
                cap = cv2.VideoCapture(public.SETTING["CAMERA"])
                ret, frame = cap.read()
                if ret:
                    break
            if foo == 30:
                print("Unable to receive frame (stream end?). Exiting ...")
                break
            else:
                continue

        # 转为灰度
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 获取亮度
        bri = cv2.mean(gray)[0]
        # print("env brightness: %s" % bri)

        # 输出结果帧
        # cv2.imshow('Frame', gray)

        # 计算推荐值
        try:
            foo = public.setMonitor(bri, bri_old, bri_recom - bri_now)
        except Exception as e:
            print(f"发生错误: {e}")
        # 环境亮度估算中
        if foo >= 0:
            bri_recom = foo
            print("Adjusting...")
            # 设置初始亮度
            if bri_now == -1:
                bri_now = bri_recom
                public.BrightnessAdjust(bri_now)
                continue
            # 设置缓冲亮度
            if public.TRANSITIONAL["SWITCH"] == 1:
                try:
                    now_bri_foo = public.transitionBrightness(bri_now, bri_recom)
                    if now_bri_foo != -2:
                        bri_now = now_bri_foo
                except Exception as e:
                    print(f"发生错误: {e}")

            bri_stable = 0
        # 亮度值稳定后
        elif foo == -2:
            if bri_now != bri_recom:
                if bri_stable < 1:
                    bri_stable += 1
                else:
                    try:
                        public.BrightnessAdjust(bri_recom)
                    except Exception as e:
                        print(f"发生错误: {e}")
                    bri_now = bri_recom
                    print("Stable now: %s" % bri_now)
                    print(public.SPLIT)
                    bri_stable = 5
            elif bri_now == bri_recom:
                if bri_stable < 3:
                    bri_stable += 1
                if bri_stable == 2:
                    print("No change: %s" % bri_now)
                    print(public.SPLIT)

        bri_old = bri

        # 按 'q' 键退出
        # if cv2.waitKey(1) == ord("q"):
        #     break

        time.sleep(public.SETTING["INTERVAL"])

    # 完成后，释放cap对象
    cap.release()
    cv2.destroyAllWindows()


# 重新启动任务
def rerun(self):
    public.open_ini("config.ini")
    # 重启线程
    global settings_updata
    settings_updata = True
    self.thread.join()  # 等待进程结束
    self.text.delete(1.0, "end")  # 清空输入框
    print("Restarting...")
    self.thread = Thread(target=background_task, args=(self.queue,), daemon=True)
    self.thread.start()
    settings_updata = False
    global settings_open
    settings_open = False


# 定义Tkinter主窗口类
class App(Tk):
    # GUI初始化代码...
    def __init__(self):
        super().__init__()
        # 初始化
        public.initialize("config.ini")

        # 设置窗口
        if public.SETTING["SHOW"] == 0:
            self.withdraw()  # 隐藏主窗口
        self.title("自动亮度")
        self.geometry("500x300")
        self.iconbitmap(public.processPath("1.ico"))
        self.text = Text(self, width=250, height=80)  # 添加一个Text用于显示文本
        self.text.pack(pady=20)  # 垂直填充一些空间
        # 禁用键盘输入，只允许 Ctrl+c 复制
        self.text.bind(
            "<Key>", lambda e: (0 if e.state == 4 and e.keycode == 67 else "break")
        )

        # 重定向标准输出到文本框
        public.redirect_stdout_to_tkinter(self.text)

        # 托盘图标创建代码...
        self.create_tray_icon()

        # 创建一个队列用于线程间通信
        self.queue = Queue()

        # 创建后台线程
        self.thread = Thread(target=background_task, args=(self.queue,))
        self.thread.daemon = True  # 设置为守护线程，确保在主线程退出时它也会退出
        self.thread.start()

    # 托盘图标创建代码...
    def create_tray_icon(self):
        def quit_window(icon: pystray.Icon):
            icon.stop()
            self.destroy()

        def show_window():
            self.deiconify()

        def on_exit():
            self.withdraw()

        def settings_tool():
            root = Tk()
            root.title("滑块控件示例")
            root.withdraw()  # 隐藏主窗口
            root.geometry("500x300")
            root.iconbitmap(public.processPath("1.ico"))
            # 创建滑块控件
            slider = ttk.Scale(
                root,
                from_=0,
                to=100,
                orient="horizontal",
                command=lambda value: print(value),
            )
            slider.pack()

            # 运行窗体
            root.mainloop()

        def settings():
            global settings_open
            if settings_open:
                self.deiconify()
                print("The settings page has opened!")
                return
            self.task_foo = Thread(target=rerun, args=(self,), daemon=True)
            self.task_foo.start()
            settings_open = True

        menu = (
            MenuItem("显示", show_window, default=True),
            MenuItem("设置", settings),
            Menu.SEPARATOR,
            MenuItem("退出", quit_window),
        )
        image = Image.open(public.processPath("1.ico"))
        icon = pystray.Icon("icon", image, "自动亮度", menu)

        # 重新定义点击关闭按钮的处理
        self.protocol("WM_DELETE_WINDOW", on_exit)

        Thread(target=icon.run, daemon=True).start()

    # 周期执行队列
    def check_queue(self):
        try:
            # 安全地从队列中获取消息并更新GUI
            message = self.queue.get_nowait()
            # 在这里更新GUI，例如通过打印到控制台或更新标签等
            print(message)

        except Empty:
            # 队列为空，不做任何操作
            pass
        finally:
            # 无论是否成功获取消息，都计划在100毫秒后再次检查队列
            self.after(100, self.check_queue)


# 创建应用实例并运行
app = App()
app.after(100, app.check_queue)  # 每100毫秒检查一次队列，用于更新GUI
app.mainloop()
