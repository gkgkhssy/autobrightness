import pystray, cv2, time

from threading import Thread
from queue import Empty, Queue
from tkinter import Text, Tk, ttk
from pystray import MenuItem, Menu
from PIL import Image
from tkinter import Scale

import public

settings_open = False  # 判断设置页面是否已打开
settings_updata = False  # 判断设置是否更新
settings_easy_updata = False  # 判断亮度设置是否更新


# 挂载任务
def background_task(q):
    # 初始化
    public.initialize("config.ini")

    # 创建VideoCapture对象，参数0表示使用默认的摄像头
    cap = cv2.VideoCapture(public.SETTING["CAMERA"])

    # 检查可用摄像头
    if not cap.isOpened():
        print("正在检查可用摄像头")
        foo = 0
        while 1:
            cap = cv2.VideoCapture(foo)
            if cap.isOpened():
                print(f"当前使用摄像头为:{foo}")
                public.SETTING["CAMERA"] = foo
                break
            elif foo < 5:
                foo += 1
            else:
                print("你没有可用摄像头")
                return

    bri_old = -1  # 上一次亮度记录值
    bri_now = -1  # 现在的屏幕亮度
    bri_recom = -100  # 推荐的屏幕亮度
    bri_stable = 0

    trans_offset_old = 0  # 上一次的屏幕偏移亮度
    trans_offset_stable = False  # 是否可以切换为黑屏幕状态

    # 逐帧捕获
    while True:
        # 设置更新退出循环
        if settings_updata:
            cap.release()
            cv2.destroyAllWindows()
            return
        global settings_easy_updata
        if settings_easy_updata:
            # 初始化参数，应用更新配置
            bri_now = -1
            bri_old = -1
            bri_recom = -100
            bri_stable = 0
            settings_easy_updata = False

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
            print(f"错误: {e}")
        # 环境亮度估算中
        if foo >= 0:
            bri_stable = 0
            bri_recom = foo
            print("调整中...")
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
                    print(f"错误: {e}")
        # 推荐亮度值稳定后
        elif foo == -2:
            if bri_now != bri_recom:
                if bri_stable < 3:
                    # 确保过亮或过暗的亮度值是真实的
                    if (
                        bri_recom
                        > public.BRIGHTNESS["MAX"] - public.BRIGHTNESS["STEP"]
                        # or bri_recom
                        # < public.BRIGHTNESS["MIN"] + public.BRIGHTNESS["STEP"]
                    ):
                        time.sleep(public.SETTING["INTERVAL"])

                    bri_stable += 1
                    print("等待亮度稳定中...")

                else:
                    try:
                        public.BrightnessAdjust(bri_recom)
                    except Exception as e:
                        print(f"错误: {e}")
                    bri_now = bri_recom
                    print("确定亮度值: %s" % bri_now)
                    print(public.SPLIT)
                    bri_stable = 6
            elif bri_now == bri_recom:
                if bri_stable < 3:
                    bri_stable += 1
                if bri_stable == 2:
                    print("稳定亮度值: %s" % bri_now)
                    print(public.SPLIT)

        bri_old = bri

        # 屏幕显示大面积浅色时自适应亮度
        if public.TRANSITIONAL["BLACK_WHITE"] == 1:
            # 获取屏幕显示内容的灰度值
            average_gray = public.getAverageGrayscale()
            # 根据屏幕灰度值适当减少亮度
            trans_offset = public.dimScreenByGrayscale(average_gray)
            if trans_offset != 2 and trans_offset != trans_offset_old:
                public.TRANSITIONAL["CORRECT"] = trans_offset
                foo = bri_now + trans_offset
                public.BrightnessAdjust(foo)
                print(f"白平衡亮度: {foo}")
                trans_offset_old = trans_offset
                trans_offset_stable = True
            elif trans_offset == 2 and trans_offset_stable:
                public.BrightnessAdjust(bri_now)
                print(f"黑平衡亮度: {bri_now}")
                public.TRANSITIONAL["CORRECT"] = trans_offset_old = 0
                trans_offset_stable = False

        # 按 'q' 键退出
        # if cv2.waitKey(1) == ord("q"):
        #     break

        time.sleep(public.SETTING["INTERVAL"])

    # 完成后，释放cap对象
    cap.release()
    cv2.destroyAllWindows()


# 重新启动任务
def rerun_settings(self):
    public.open_ini("config.ini")
    # 重启线程
    global settings_updata
    settings_updata = True

    self.thread.join()  # 等待进程结束
    self.text.delete(1.0, "end")  # 清空输入框
    print("重启中...")
    self.thread = Thread(target=background_task, args=(self.queue,), daemon=True)
    self.thread.start()

    settings_updata = False
    global settings_open
    settings_open = False


# 简单设置选项
def run_settings_easy(self):
    root = Tk()
    # root.attributes("-toolwindow", 2) # 去掉窗口最大化最小化按钮，只保留关闭
    root.title("设置")
    root.geometry("+500+300")
    root.iconbitmap(public.processPath("1.ico"))
    # 创建滑块控件
    brightness_discrete = Scale(
        root,
        label="亮度变化幅度（更小或更大）",
        length=300,
        width=20,
        from_=0.1,
        to=10,
        orient="horizontal",
        # tickinterval=1,
        resolution=0.1,
    )
    brightness_discrete.set(public.BRIGHTNESS["DISCRETE"])
    brightness_discrete.pack()

    brightness_threshold = Scale(
        root,
        label="更暗或更亮的分界点（亮度值）",
        length=300,
        width=20,
        from_=public.BRIGHTNESS["MIN"],
        to=public.BRIGHTNESS["MAX"],
        orient="horizontal",
        resolution=1,
    )
    brightness_threshold.set(public.BRIGHTNESS["THRESHOLD"])
    brightness_threshold.pack()

    # 实时应用参数
    def discrete_set(val):
        public.BRIGHTNESS["DISCRETE"] = float(val)
        global settings_easy_updata
        settings_easy_updata = True

    def correct_set(val):
        # val += (public.BRIGHTNESS["MAX"] - public.BRIGHTNESS["MIN"]) / 2
        public.BRIGHTNESS["THRESHOLD"] = int(val)
        global settings_easy_updata
        settings_easy_updata = True

    brightness_discrete.bind(
        "<ButtonRelease-1>", lambda e: discrete_set(brightness_discrete.get())
    )

    brightness_threshold.bind(
        "<ButtonRelease-1>", lambda e: correct_set(brightness_threshold.get())
    )

    root.mainloop()

    # 关闭窗口后保存参数
    try:
        public.apply_settings_easy("config.ini")
        print("设置已保存")
    except Exception as e:
        print(f"错误: {e}")
    print(public.SPLIT)

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

        # 简单设置
        def settings_easy():
            global settings_open
            if settings_open:
                self.deiconify()
                print("当前已有设置界面被打开！")
                return
            self.settings_easy = Thread(
                target=run_settings_easy, args=(self,), daemon=True
            )
            self.settings_easy.start()
            settings_open = True

        # 完整设置
        def settings():
            global settings_open
            if settings_open:
                self.deiconify()
                print("当前已有设置界面被打开！")
                return
            self.settings = Thread(target=rerun_settings, args=(self,), daemon=True)
            self.settings.start()
            settings_open = True

        # 菜单选项
        menu = (
            MenuItem("显示", show_window, default=True),
            MenuItem("设置", settings_easy),
            MenuItem("更多", settings),
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
