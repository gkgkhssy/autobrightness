import pystray, cv2, time, ctypes

from threading import Thread
from queue import Empty, Queue
from tkinter import Text, Tk, Scale
from pystray import MenuItem, Menu
from PIL import Image

import public

ERROR_ALREADY_EXISTS = 183
_mutex_name = "Global\\MyAutoBrightnessApp_Mutex"  # 唯一应用名
is_first_instance = False

settings_open = False  # 判断设置页面是否已打开
settings_updata = False  # 判断设置是否更新
settings_easy_updata = False  # 判断亮度设置是否更新
blackWhite_run = False  # 判断根据屏幕灰白动态亮度是否已打开

bri_now = -1  # 现在的屏幕亮度


# 挂载任务
def background_task(q):
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
    else:
        print(f"当前使用摄像头为:{public.SETTING['CAMERA']}")

    bri_old = -1  # 上一次亮度记录值
    global bri_now  # 现在的屏幕亮度
    bri_recom = -100  # 推荐的屏幕亮度
    bri_stable = 0

    # 逐帧捕获
    while True:
        # 设置更新退出循环
        if settings_updata:
            break
        global settings_easy_updata
        if settings_easy_updata:
            # 初始化参数，应用更新配置
            bri_now = -1
            bri_old = -1
            bri_recom = -100
            bri_stable = 0
            settings_easy_updata = False

        # 使用带超时的读取，避免在摄像头无响应（如合盖后）时阻塞
        def _read_with_timeout(cam, timeout=2):
            qret = Queue(maxsize=1)

            def _read():
                try:
                    r, f = cam.read()
                    qret.put((r, f))
                except Exception:
                    try:
                        qret.put((False, None))
                    except Exception:
                        pass

            th = Thread(target=_read, daemon=True)
            th.start()
            try:
                return qret.get(timeout=timeout)
            except Empty:
                return False, None

        ret, frame = _read_with_timeout(cap, timeout=2)
        # 如果读取失败，尝试重连。记录连续失败次数，超过阈值时重建摄像头
        if not ret:
            if not hasattr(background_task, "_fail_count"):
                background_task._fail_count = 0
            background_task._fail_count += 1
            # public.log(f"摄像头读取失败 (count={background_task._fail_count})")
            # 小范围短暂等待后重试
            if background_task._fail_count < 3:
                time.sleep(1)
                continue

            # 到达重连阈值，尝试重建摄像头
            public.log("读取失败，尝试释放并重建摄像头")
            try:
                cap.release()
            except Exception as e:
                public.log(f"释放摄像头时出错: {e}")

            found = False
            # 先尝试当前索引，若失败遍历0-5并尝试不同后端
            backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
            for backend in backends:
                for idx in range(0, 6):
                    # public.log(f"尝试打开摄像头 idx={idx} backend={backend}")
                    try:
                        cap = cv2.VideoCapture(idx, backend)
                        if cap.isOpened():
                            public.SETTING["CAMERA"] = idx
                            public.log(
                                f"重建成功，使用摄像头 {idx} (backend={backend})"
                            )
                            found = True
                            break
                        else:
                            try:
                                cap.release()
                            except Exception:
                                pass
                    except Exception as e:
                        public.log(f"尝试打开摄像头时抛出异常: {e}")
                if found:
                    break

            if not found:
                num = 10
                public.log(f"未找到可用摄像头，等待{num}秒后重试")
                background_task._fail_count = 0
                time.sleep(num)
                continue

            # 重建成功，清零失败计数并继续
            background_task._fail_count = 0
            # 继续下一轮读取
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

        # 按 'q' 键退出
        # if cv2.waitKey(1) == ord("q"):
        #     break

        time.sleep(public.SETTING["INTERVAL"])

    # 完成后，释放cap对象
    cap.release()
    cv2.destroyAllWindows()


# 通过屏幕显示内容动态改变亮度任务
def dim_screen_by_grayscale_task(q):
    trans_offset_old = 0  # 上一次的屏幕偏移亮度
    trans_offset_stable = False  # 是否可以切换为黑屏幕状态
    global bri_now  # 现在的屏幕亮度

    while True:
        """屏幕显示大面积浅色时自适应亮度"""
        if settings_updata:
            return
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

        # 因为及时性要求高，所以取固定检测频率
        time.sleep(0.1)


# 重新启动任务
def rerun_settings(self):
    public.open_ini("config.ini")
    # 重启线程
    global settings_updata
    settings_updata = True

    # 等待进程结束
    self.thread1.join()
    global blackWhite_run
    if blackWhite_run:
        self.thread2.join()
    self.text.delete(1.0, "end")  # 清空输入框
    settings_updata = False

    print("重启中...")
    public.initialize("config.ini")  # 初始化
    # 重启线程
    self.thread1 = Thread(target=background_task, args=(self.queue,), daemon=True)
    self.thread1.start()
    if public.TRANSITIONAL["BLACK_WHITE"] == 1:
        self.thread2 = Thread(
            target=dim_screen_by_grayscale_task, args=(self.queue,), daemon=True
        )
        self.thread2.start()
        blackWhite_run = True
    else:
        blackWhite_run = False

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
        label="更亮或更暗的分界点（环境亮度值）",
        length=300,
        width=20,
        # from_=public.BRIGHTNESS["MIN"],
        # to=public.BRIGHTNESS["MAX"],
        from_=0,
        to=100,
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


# 创建主窗口
def create_window(self):
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


# 检查单实例
def check_instance():
    _handle = ctypes.windll.kernel32.CreateMutexW(
        None, ctypes.wintypes.BOOL(True), _mutex_name
    )
    if ctypes.windll.kernel32.GetLastError() != ERROR_ALREADY_EXISTS:
        global is_first_instance
        is_first_instance = True


# 非单实例警告
def non_singleton_warning_task(self):
    self.deiconify()
    print("程序已在运行，不要重复启动，即将退出...")
    time.sleep(2)
    self.destroy()
    # sys.exit(0)


# 创建后台线程
def create_background_thread(self):
    # 创建非单实例警告线程
    if not is_first_instance:
        self.thread0 = Thread(
            target=non_singleton_warning_task, args=(self,), daemon=True
        )
        self.thread0.start()
        return

    # 创建后台任务线程
    self.thread1 = Thread(target=background_task, args=(self.queue,))
    self.thread1.daemon = True  # 设置为守护线程，确保在主线程退出时它也会退出
    self.thread1.start()
    # 通过屏幕显示内容动态改变亮度任务
    if public.TRANSITIONAL["BLACK_WHITE"] == 1:
        self.thread2 = Thread(
            target=dim_screen_by_grayscale_task, args=(self.queue,), daemon=True
        )
        self.thread2.start()
        global blackWhite_run
        blackWhite_run = True


# 定义Tkinter主窗口类
class App(Tk):
    # GUI初始化代码...
    def __init__(self):
        super().__init__()

        # 设置窗口
        create_window(self)

        # 重定向标准输出到文本框
        public.redirect_stdout_to_tkinter(self.text)

        # 检查是否为第一个实例
        check_instance()

        # 初始化配置
        public.initialize("config.ini")

        # 显示控制台
        if public.SETTING["SHOW"] == 1:
            self.deiconify()

        # 托盘图标创建代码...
        self.create_tray_icon()

        # 创建一个队列用于线程间通信
        self.queue = Queue()

        # 创建后台线程
        create_background_thread(self)

    # 托盘图标创建代码...
    def create_tray_icon(self):
        def quit_window():
            self.withdraw()

        def show_window():
            self.deiconify()

        def on_exit(icon):
            icon.stop()
            self.destroy()

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
            MenuItem("退出", on_exit),
        )
        image = Image.open(public.processPath("1.ico"))
        icon = pystray.Icon("icon", image, "自动亮度", menu)

        # 重新定义点击关闭按钮的处理
        self.protocol("WM_DELETE_WINDOW", quit_window)

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
