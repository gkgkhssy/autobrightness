import wmi, math, sys, os, subprocess, tempfile, shutil, pyautogui
import numpy as np
from configparser import ConfigParser

SETTING = {}
BRIGHTNESS = {}
TRANSITIONAL = {}
SPLIT = "-----------------------------"


# 解决打包后调用文件问题
def processPath(path):
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


# 保留注释，修改单行键值，
def update_ini_file(ini_file, section, option, new_value):
    # 创建一个临时文件用于存储修改后的内容
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmpfile:
        # 读取INI文件并处理注释
        with open(ini_file, "r", encoding="utf-8") as file:
            in_section = False
            for line in file:
                # 检查是否是新节的开始
                if line.strip().startswith("["):
                    section_name = line.strip()[1:-1]
                    in_section = section_name == section
                    tmpfile.write(line)
                    continue

                # 如果当前行在目标节中，并且是要修改的选项，则修改它
                if in_section and "=" in line:
                    key, value = line.split("=", 1)
                    if key.strip() == option:
                        tmpfile.write(f"{key.strip()} = {new_value}\n")
                        continue

                # 否则，将当前行（注释或空白行）写入临时文件
                tmpfile.write(line)

        # 将修改后的内容写回原始文件（或新文件，如果需要保留原始文件）
        tmp_path = tmpfile.name

    # 使用shutil确保文件被正确关闭和替换
    with open(ini_file, "w", encoding="utf-8") as file:
        with open(tmp_path, "r") as tmpfile:
            shutil.copyfileobj(tmpfile, file)

    # 删除临时文件
    os.remove(tmp_path)


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
    BRIGHTNESS["DISCRETE"] = config["brightness"].getfloat("discrete")
    BRIGHTNESS["THRESHOLD"] = config["brightness"].getfloat("threshold")
    BRIGHTNESS["LOW_BRIGHTNESS"] = config["brightness"].getint("low_brightness")
    BRIGHTNESS["LOW_CORRECT"] = config["brightness"].getfloat("low_correct")
    BRIGHTNESS["HIGH_BRIGHTNESS"] = config["brightness"].getint("high_brightness")
    BRIGHTNESS["HIGH_CORRECT"] = config["brightness"].getfloat("high_correct")
    BRIGHTNESS["CORRECT"] = config["brightness"].getint("correct")

    TRANSITIONAL["SWITCH"] = config["transitional"].getint("switch")
    TRANSITIONAL["WEIGHTS"] = config["transitional"].getfloat("weights")
    TRANSITIONAL["BLACK_WHITE"] = config["transitional"].getint("black_white")
    TRANSITIONAL["AMPLITUDE"] = config["transitional"].getfloat("amplitude")
    TRANSITIONAL["CORRECT"] = 0
    return True


# 修改部分配置文件参数
def apply_settings_easy(file_path):
    # config = ConfigParser()
    # config.read(file_path, encoding="utf-8")
    # config.set("brightness", "weights", str(BRIGHTNESS["WEIGHTS"]))
    # config.set("brightness", "correct", str(BRIGHTNESS["CORRECT"]))
    # with open(file_path, "w") as f:
    #     config.write(f)

    update_ini_file(file_path, "brightness", "discrete", str(BRIGHTNESS["DISCRETE"]))
    update_ini_file(file_path, "brightness", "threshold", str(BRIGHTNESS["THRESHOLD"]))


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
            """# 配置文件，删除该文件后重新生成默认配置，注意亮度值需取整
;---------------------------------------------------------------------------------------
[setting]
# 如果连接了多个摄像头或虚拟摄像头，修改此项切换调用的摄像头。默认 0
# 如果需要使用摄像头，需要暂时将程序退出解除摄像头占用，或切换成其他不常用的摄像头。
# 取 -1 时自动检测可用摄像头
camera = 0

# 每隔多少秒执行一次判断，过快影响性能和判断拟合，过慢响应延迟较高。
interval = 0.3

# 每次启动程序是否自动打开控制台。
# 开启 1，关闭 0
show = 1
;---------------------------------------------------------------------------------------
[brightness]
# 定义自动调节的亮度最小和最大值。
# 如果不需要更低的亮度可以适当提高 min，不需要更高的亮度则适当降低 max
min = 0
max = 100

# 计算权值（推荐1.5-4，该系数越小，环境亮度越高则屏幕更亮）
# 亮度不够则调低，过亮则调高
# 该值几乎不会影响最低亮度
weights = 2.55

# 亮度的静态和动态防抖值
# 如果希望程序对环境亮度变化更敏感，可以适当减少 step
# 如果屏幕亮度一直处于变化，无法稳定，适当增加 step
# 如果控制台一直在调整亮度(Adjusting...)，适当增加 change_step
# 如果对每次调整的亮度浮动过大不满意，适当减少 change_step
step = 10
change_step = 2

# 修改优先级第一
# 离散值（推荐0-2，该系数越大，亮度越容易偏向更暗或更亮）
# 如果环境亮度低则屏幕亮度更低，环境亮度高则屏幕亮度更高，取0则不生效
discrete = 1.0

# 修改优先级第二
# 判断高亮度与低亮度之间的临界点亮度，取亮度 min 和 max 之间的合适值
threshold = 50.0
;---------------------------------------------------------------------------------------
# 低亮度阈值与修正值
# 如果需要在某个亮度值以下更亮或更暗，先确保 low_correct 为 0
# 观察控制台稳定后亮度值，一般将该值+5确保范围生效，然后填入 low_brightness
# 如果低于这个范围，需要更低亮度可以填 -10，更亮则填 10，可以适当取值
low_brightness = 55
low_correct = 0

# 高亮度阈值与修正值
# 如果需要在某个亮度值以上更亮或更暗，先确保 high_correct 为 0
# 观察控制台稳定后亮度值，一般将该值-5确保范围生效，然后填入 high_brightness
# 如果高于这个范围，需要更低亮度可以填 -10，更亮则填 10，可以适当取值
high_brightness = 75
high_correct = 0

# 亮度总偏移值
# 如果需要最终亮度整体增加或减少一个固定值，修改此项
correct = 0
;---------------------------------------------------------------------------------------
[transitional]
# 亮度剧烈变化时，启动亮度过渡估算，加快响应速度
# 开启 1，关闭 0
switch = 1

# 计算权值（推荐1.5-3，该系数越小，估值越激进）
# 如果希望环境亮度变化剧烈时，屏幕亮度变化跨幅更大，可以填 1.5
# 如果希望环境亮度变化剧烈时，屏幕亮度变化跨幅更小，可以填 3
weights = 2.0
;---------------------------------------------------------------------------------------
# 当屏幕显示核心区间内容由主暗色转变为主亮色时，适当降低屏幕亮度
# 开启 1，关闭 0
black_white = 0

# 变化幅度（推荐0.5-2，系数越大变化幅度越大）
amplitude = 1.0
"""
        )
    print("成功初始化配置文件")


# 程序初始化启动，读取并应用配置
def initialize(file_path):
    # 读取配置文件
    config = read_config(file_path)
    # 配置文件不存在则创建后再读取
    if config == False:
        create_config_file(file_path)
        config = read_config(file_path)
    if apply_config(config):
        print("成功读取配置文件")
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
        print(f"环境亮度: {math.ceil(Brightness)}")
        Brightness += (Brightness - BRIGHTNESS["THRESHOLD"]) * BRIGHTNESS["DISCRETE"]
        Brightness = min(max(Brightness, BRIGHTNESS["MIN"]), BRIGHTNESS["MAX"])
        if Brightness <= BRIGHTNESS["LOW_BRIGHTNESS"]:
            Brightness += BRIGHTNESS["LOW_CORRECT"]
        if Brightness >= BRIGHTNESS["HIGH_BRIGHTNESS"]:
            Brightness += BRIGHTNESS["HIGH_CORRECT"]
        Brightness += BRIGHTNESS["CORRECT"]
        Brightness += TRANSITIONAL["CORRECT"]
        Brightness = min(max(Brightness, BRIGHTNESS["MIN"]), BRIGHTNESS["MAX"])
        Brightness = math.ceil(Brightness)
        print("推算值: %s" % Brightness)
        return Brightness
    else:
        return -2


# 亮度剧烈变化时，初步估算并适应亮度
def transitionBrightness(now, recom):
    if abs(now - recom) < BRIGHTNESS["STEP"] * 2:
        return -2
    change = (recom - now) / TRANSITIONAL["WEIGHTS"]
    # 过矫修正
    if change > BRIGHTNESS["STEP"] * 2:
        change -= BRIGHTNESS["STEP"] * 2
    elif 0 - change > BRIGHTNESS["STEP"] * 2:
        change += BRIGHTNESS["STEP"] * 2
    now += change
    now = math.ceil(now)
    print(f"当前过渡亮度: {now}")
    BrightnessAdjust(now)
    return now


# 获取屏幕显示内容的灰度值
def getAverageGrayscale(
    region=(
        int(pyautogui.size().width / 4),
        int(pyautogui.size().height / 4),
        int(pyautogui.size().width / 2),
        int(pyautogui.size().height / 2),
    )
):
    # 捕获屏幕图像或指定区域的图像
    screenshot = pyautogui.screenshot(region=region)

    # 将图像转换为灰度图像
    gray_image = screenshot.convert("L")

    # 使用numpy数组来处理图像数据
    gray_array = np.array(gray_image)

    # 计算所有像素值的平均值
    average_gray = np.mean(gray_array)

    return average_gray


# 根据屏幕灰度值计算应适当减少的亮度
def dimScreenByGrayscale(greyness):
    if greyness < 155:
        return 2

    greyness /= 25.5
    greyness *= TRANSITIONAL["AMPLITUDE"]
    greyness = 0 - math.floor(greyness)
    return greyness
