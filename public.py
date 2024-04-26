import wmi, math, sys, os, subprocess

from configparser import ConfigParser

SETTING = {}
BRIGHTNESS = {}
SPLIT = "-----------------------------"


# 解决打包后调用文件问题
def processPath(path):
    """
    :param path: 相对于根目录的路径
    :return: 拼接好的路径
    """
    if getattr(
        sys, "frozen", False
    ):  # 判断是否存在属性frozen，以此判断是打包的程序还是源代码。false为默认值，即没有frozen属性时返回false
        base_path = sys._MEIPASS  # 该属性也是打包程序才会有，源代码尝试获取该属性会报错
    else:
        base_path = os.path.abspath(".")  # 当源代码运行时使用该路径
    return os.path.join(base_path, path)


# 重定向标准输出到文本框
def redirect_stdout_to_tkinter(text_widget):
    class StdoutRedirector:
        def __init__(self, text_widget):
            self.text_widget = text_widget

        def write(self, message):
            self.text_widget.insert("end", message)
            self.text_widget.see("end")

    sys.stdout = StdoutRedirector(text_widget)


# 读取配置文件
def read_config(config_file):
    if not os.path.exists(config_file):
        return False
    config = ConfigParser()
    config.read(config_file, encoding="utf-8")
    return config


# 调用记事本打开文件
def open_ini(file_path):
    try:
        subprocess.call(
            f"notepad.exe {file_path}", creationflags=subprocess.CREATE_NO_WINDOW
        )

        # 不阻塞进程调用方法
        # subprocess.Popen(
        #     ["notepad.exe", file_path], creationflags=subprocess.CREATE_NO_WINDOW
        # )
    except Exception as e:
        print(f"打开文件时出错：{e}")


# 应用配置文件参数
def apply_config(config):
    # 设置参数
    SETTING["CAMERA"] = config["setting"].getint("camera")
    SETTING["INTERVAL"] = config["setting"].getfloat("interval")
    SETTING["SHOW"] = config["setting"].getint("show")

    BRIGHTNESS["MIN"] = config["brightness"].getint("min")
    BRIGHTNESS["MAX"] = config["brightness"].getint("max")
    BRIGHTNESS["STEP"] = config["brightness"].getfloat("step")
    BRIGHTNESS["CHANGE_STEP"] = config["brightness"].getfloat("change_step")
    BRIGHTNESS["WEIGHTS"] = config["brightness"].getfloat("weights")
    BRIGHTNESS["LOW_BRIGHTNESS"] = config["brightness"].getint("low_brightness")
    BRIGHTNESS["LOW_CORRECT"] = config["brightness"].getfloat("low_correct")
    BRIGHTNESS["HIGH_BRIGHTNESS"] = config["brightness"].getint("high_brightness")
    BRIGHTNESS["HIGH_CORRECT"] = config["brightness"].getfloat("high_correct")
    BRIGHTNESS["TRANSITIONAL"] = config["brightness"].getfloat("transitional")
    BRIGHTNESS["CORRECT"] = config["brightness"].getfloat("correct")
    return True


# 初始化配置文件
def create_config_file(filename):
    # 创建一个ConfigParser对象
    # config = configparser.ConfigParser()

    # 添加节
    # config["setting"] = {"camera": 1, "interval": 0.5}
    # config["brightness"] = {
    #     "min": 0,
    #     "max": 100,
    # }

    # 写入配置文件
    with open(filename, "w", encoding="utf-8") as configfile:
        configfile.write(
            """# 配置文件，删除该文件后重新生成默认配置，注意亮度值取整
[setting]
# 选择摄像头，默认 0
camera = 0
# 判断周期，间隔多少秒执行一次判断
interval = 0.3
# 启动时自动打开控制台
show = 1

[brightness]
# 定义亮度的最大和最小值
min = 0
max = 100
# 亮度的静态和动态防抖值
step = 10
change_step = 2
# 计算权值（取值1.5-2.5，该系数越小，环境亮度越高则屏幕更亮）
weights = 2.1
# 低亮度阈值与修正值
low_brightness = 55
low_correct = 0
# 高亮度阈值与修正值
high_brightness = 75
high_correct = 0
# 亮度剧烈变化时,初步取值权值（取值1.5-4，该系数越小，估值越激进）
transitional = 2
# 亮度总偏移值
correct = 0
"""
        )


# 程序初始化启动，读取并应用配置
def initialize(file_path):
    # 读取配置文件
    config = read_config(file_path)
    # 配置文件不存在则创建后再读取
    if config == False:
        create_config_file(file_path)
        config = read_config(file_path)
    if apply_config(config):
        print("The parameters are configured")
        print(SPLIT)
    else:
        print(f"There was an error in the {file_path} file")


# 修改亮度
def BrightnessAdjust(brightness_level):
    c = wmi.WMI(namespace="root\\WMI")
    methods = c.WmiMonitorBrightnessMethods()
    if methods:
        a = methods[0]
        a.WmiSetBrightness(brightness_level, Timeout=500)
    else:
        print("No brightness methods found.")


# 计算精确亮度值
def setMonitor(envLx, old_envLx, change):
    # 判断亮度是否产生变化
    if change == 0:
        foo = abs(envLx - old_envLx) > BRIGHTNESS["STEP"]
    elif change != 0:
        foo = abs(envLx - old_envLx) > BRIGHTNESS["CHANGE_STEP"]
    # 转换为推荐亮度值
    if foo:
        Brightness = envLx / BRIGHTNESS["WEIGHTS"]
        if Brightness < BRIGHTNESS["LOW_BRIGHTNESS"]:
            Brightness += BRIGHTNESS["LOW_CORRECT"]
        if Brightness > BRIGHTNESS["HIGH_BRIGHTNESS"]:
            Brightness += BRIGHTNESS["HIGH_CORRECT"]
        Brightness += BRIGHTNESS["CORRECT"]
        Brightness = min(max(Brightness, BRIGHTNESS["MIN"]), BRIGHTNESS["MAX"])
        Brightness = math.ceil(Brightness)
        print("Current: %s" % Brightness)
        return Brightness
    else:
        return -2


# 亮度剧烈变化时，初步估算并适应亮度
def transitionBrightness(now, recom):
    if abs(now - recom) < BRIGHTNESS["STEP"] * 2:
        return -2
    change = (recom - now) / BRIGHTNESS["TRANSITIONAL"]
    # 过矫修正
    if change > BRIGHTNESS["STEP"] * 2:
        change -= BRIGHTNESS["STEP"] * 2
    elif 0 - change > BRIGHTNESS["STEP"] * 2:
        change += BRIGHTNESS["STEP"] * 2
    now += change
    now = math.ceil(now)
    print(f"Transition now:{now}")
    BrightnessAdjust(now)
    return now
