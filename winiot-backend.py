import os
import subprocess
from functools import wraps
from flask import Flask, jsonify, abort, request
import shutil  # 用于 shutil.which
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv # 用于加载 .env 文件

# 尝试加载 .env 文件 (如果存在)
# 确保 .env 文件与 app.py 在同一目录，或者在打包后与 .exe 在同一目录
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(dotenv_path):
    print(f"Loading .env file from: {dotenv_path}")
    load_dotenv(dotenv_path=dotenv_path)
else:
    print("No .env file found. Using default configurations.")


# --- Core Application Setup ---
app = Flask(__name__)

# --- Configuration from .env or Defaults ---
# API Authentication
# 默认不启用API鉴权
API_AUTH_ENABLED_STR = os.getenv('API_AUTH_ENABLED', 'False') # 默认 'False'
app.config['API_AUTH_ENABLED'] = API_AUTH_ENABLED_STR.lower() == 'true'
app.config['EXPECTED_API_KEY'] = os.getenv('API_KEY', 'you_should_really_set_a_key_if_auth_is_enabled')

# Flask Server Settings
# 默认监听所有IP (0.0.0.0) 和 5000 端口
FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))
FLASK_DEBUG_MODE = os.getenv('FLASK_DEBUG', 'False').lower() == 'true' # 生产环境应为 False

# Twinkle Tray Path Configuration
# 优先使用环境变量 TWINKLE_TRAY_PATH
TWINKLE_TRAY_ENV_PATH = os.getenv('TWINKLE_TRAY_PATH')
twinkle_tray_base_path = "Twinkle Tray.exe" # 最终回退，依赖 PATH
twinkle_tray_base_path_found = False

if TWINKLE_TRAY_ENV_PATH and os.path.exists(TWINKLE_TRAY_ENV_PATH):
    twinkle_tray_base_path = TWINKLE_TRAY_ENV_PATH
    twinkle_tray_base_path_found = True
    # print(f"Using Twinkle Tray from TWINKLE_TRAY_PATH: {twinkle_tray_base_path}")
else:
    local_app_data = os.getenv('LOCALAPPDATA')
    if local_app_data:
        paths_to_check = [
            os.path.join(local_app_data, "Programs", "twinkle-tray", "Twinkle Tray.exe"),
            os.path.join(local_app_data, "twinkle-tray", "Twinkle Tray.exe")
        ]
        for path in paths_to_check:
            if os.path.exists(path):
                twinkle_tray_base_path = path
                twinkle_tray_base_path_found = True
                break
    # 如果上述路径都未找到，则会使用默认的 "Twinkle Tray.exe" (依赖PATH)

# --- Logging Setup ---
log_dir = os.path.dirname(os.path.abspath(__file__)) # 日志文件与脚本/exe同目录
log_file_path = os.path.join(log_dir, 'flask_api.log')

# 确保日志目录存在 (如果日志文件在子目录中)
# if not os.path.exists(log_dir):
#    os.makedirs(log_dir)

log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s')
# 使用 RotatingFileHandler 实现日志轮转
file_handler = RotatingFileHandler(log_file_path, mode='a', maxBytes=5*1024*1024, # 5 MB
                                 backupCount=3, encoding='utf-8', delay=False)
file_handler.setFormatter(log_formatter)

# 配置 Flask 的 logger 和 Werkzeug logger (Waitress 使用自己的日志，但Flask内部仍用werkzeug)
if FLASK_DEBUG_MODE: # 开发模式下日志级别更低
    log_level = logging.DEBUG
    # 在调试模式下也输出到控制台
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    app.logger.addHandler(console_handler)
    logging.getLogger('werkzeug').addHandler(console_handler)
else:
    log_level = logging.INFO

app.logger.addHandler(file_handler)
app.logger.setLevel(log_level)
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.addHandler(file_handler)
werkzeug_logger.setLevel(log_level) # 通常INFO级别足够

app.logger.info("Flask API application starting...")
app.logger.info(f"API Auth Enabled: {app.config['API_AUTH_ENABLED']}")
if app.config['API_AUTH_ENABLED']:
    app.logger.info(f"API Key configured (length): {len(app.config['EXPECTED_API_KEY'])}")
app.logger.info(f"Twinkle Tray Path: {twinkle_tray_base_path} (Found: {twinkle_tray_base_path_found or bool(shutil.which(twinkle_tray_base_path))})")


# --- COM and pycaw Setup ---
try:
    import pythoncom
except ImportError:
    app.logger.warning("pythoncom module not found. If pycaw audio functions fail with CoInitialize error, try 'pip install pywin32'.")
    pythoncom = None
try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
except ImportError:
    app.logger.error("pycaw library or its components not found. Audio control features will be disabled. Please run 'pip install pycaw'.")
    AudioUtilities = None
    IAudioEndpointVolume = None


# --- Authentication Decorator ---
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if app.config.get('API_AUTH_ENABLED', False):
            api_key = request.headers.get('X-API-Key')
            expected_key = app.config.get('EXPECTED_API_KEY')
            if not api_key:
                app.logger.warning(f"Access denied to {request.path}: No API key provided.")
                abort(401, description="API key required. Please provide it in the 'X-API-Key' header.")
            if api_key != expected_key:
                app.logger.warning(f"Access denied to {request.path}: Invalid API key.")
                abort(403, description="Invalid API key.")
        return f(*args, **kwargs)
    return decorated_function

# --- Helper Functions for subprocess ---
def run_command(command_parts):
    app.logger.debug(f"Executing command: {command_parts}")
    try:
        creationflags = 0
        if command_parts[0].lower() == 'powershell':
            creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            
        process = subprocess.Popen(command_parts, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', shell=False, creationflags=creationflags)
        stdout, stderr = process.communicate(timeout=15)
        if process.returncode == 0:
            app.logger.info(f"Command successful: {command_parts} -> Output: {stdout.strip() or 'No output'}")
            return True, stdout.strip() or "命令成功执行。"
        else:
            error_message = stderr.strip() or stdout.strip() or f"未知错误 (返回码: {process.returncode})"
            app.logger.error(f"Command failed: {command_parts} -> Error: {error_message}")
            return False, f"执行命令出错: {error_message}"
    except FileNotFoundError:
        app.logger.error(f"Executable not found: {command_parts[0]}")
        return False, f"错误：可执行文件 '{command_parts[0]}' 未找到。"
    except subprocess.TimeoutExpired:
        app.logger.warning(f"Command timed out: {command_parts}")
        if 'process' in locals() and process: process.kill(); process.communicate()
        return False, "命令执行超时。"
    except Exception as e:
        app.logger.exception(f"Unexpected error during command execution: {command_parts}")
        return False, f"发生意外错误: {str(e)}"

# --- Twinkle Tray: 单个显示器 VCP 电源控制 ---
def get_twinkle_power_command_parts(monitor_num, power_state_vcp):
    if not twinkle_tray_base_path_found and not shutil.which(twinkle_tray_base_path):
         app.logger.warning(f"Twinkle Tray executable '{twinkle_tray_base_path}' not found.")
         return None, f"Twinkle Tray 可执行文件 '{twinkle_tray_base_path}' 未找到。"
    if not isinstance(monitor_num, int) or monitor_num <= 0:
        return None, "显示器编号必须是一个正整数。"
    return [twinkle_tray_base_path, f"--MonitorNum={monitor_num}", f"--VCP={power_state_vcp}"], None

@app.route('/api/monitor/<int:monitor_num>/on', methods=['POST', 'GET'])
@require_api_key
def monitor_on_vcp(monitor_num):
    command_parts, error = get_twinkle_power_command_parts(monitor_num, "0xD6:1")
    if error: return jsonify({"status": "error", "message": error}), 400
    success, message = run_command(command_parts)
    if success: return jsonify({"status": "success", "monitor_num": monitor_num, "action": "MONITOR_ON_VCP", "message": "显示器已通过 VCP 命令打开。", "details": message}), 200
    return jsonify({"status": "error", "monitor_num": monitor_num, "action": "MONITOR_ON_VCP", "message": "通过 VCP 命令打开显示器失败。", "details": message}), 500

@app.route('/api/monitor/<int:monitor_num>/off', methods=['POST', 'GET'])
@require_api_key
def monitor_off_vcp(monitor_num):
    command_parts, error = get_twinkle_power_command_parts(monitor_num, "0xD6:5") 
    if error: return jsonify({"status": "error", "message": error}), 400
    success, message = run_command(command_parts)
    if success: return jsonify({"status": "success", "monitor_num": monitor_num, "action": "MONITOR_OFF_VCP", "message": "显示器已通过 VCP 命令关闭/待机。", "details": message}), 200
    return jsonify({"status": "error", "monitor_num": monitor_num, "action": "MONITOR_OFF_VCP", "message": "通过 VCP 命令关闭/待机显示器失败。", "details": message}), 500

# --- Twinkle Tray: 亮度控制 ---
def get_twinkle_brightness_command_parts(monitor_num_input, brightness_level):
    if not twinkle_tray_base_path_found and not shutil.which(twinkle_tray_base_path):
         app.logger.warning(f"Twinkle Tray executable '{twinkle_tray_base_path}' not found.")
         return None, f"Twinkle Tray 可执行文件 '{twinkle_tray_base_path}' 未找到。"
    valid_brightness = isinstance(brightness_level, int) and 0 <= brightness_level <= 100
    if not valid_brightness: return None, "亮度值必须是 0 到 100 之间的整数。"

    try:
        monitor_num = int(monitor_num_input)
        if monitor_num == 0: # Convention for "all monitors"
            return [twinkle_tray_base_path, "--AllMonitors", f"--Set={brightness_level}"], None
        elif monitor_num > 0:
            return [twinkle_tray_base_path, f"--MonitorNum={monitor_num}", f"--Set={brightness_level}"], None
        else: # Negative numbers are invalid
            return None, "显示器编号不能为负数。"
    except ValueError: # monitor_num_input was not an int (e.g. "all")
        if str(monitor_num_input).lower() == "all":
             return [twinkle_tray_base_path, "--AllMonitors", f"--Set={brightness_level}"], None
        else:
            return None, f"无效的显示器编号: '{monitor_num_input}'。应为正整数, 0, 或 'all'。"

@app.route('/api/monitor/<path:monitor_num_str>/brightness/<int:level>', methods=['POST', 'GET'])
@require_api_key
def set_monitor_brightness(monitor_num_str, level):
    target_description = f"显示器 {monitor_num_str}" if monitor_num_str.isdigit() and int(monitor_num_str) > 0 else "所有显示器"
    
    command_parts, error = get_twinkle_brightness_command_parts(monitor_num_str, level)
    if error: 
        app.logger.error(f"Brightness command generation error for monitor '{monitor_num_str}', level {level}: {error}")
        return jsonify({"status": "error", "message": error}), 400
    
    success, message = run_command(command_parts)
    if success: 
        return jsonify({"status": "success", "target": target_description, "brightness_level": level, "message": f"{target_description} 亮度已设置为 {level}%。", "details": message}), 200
    return jsonify({"status": "error", "target": target_description, "brightness_level": level, "message": f"设置 {target_description} 亮度为 {level}% 失败。", "details": message}), 500

# --- 系统音频控制 (pycaw) ---
def _get_master_volume_control():
    if AudioUtilities is None or IAudioEndpointVolume is None:
        return None, "pycaw 库或其必要组件未加载。"
    com_initialized_here = False
    if pythoncom:
        try:
            hr = pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
            if hr == 0 or hr == 1: com_initialized_here = True
            elif hr == -2147417850: pass 
        except AttributeError: pass 
        except Exception as e:
            if "already initialized" not in str(e).lower() and "RPC_E_CHANGED_MODE" not in str(e).upper():
                 app.logger.error(f"COM initialization failed: {e}")
                 return None, f"COM 初始化失败: {e}"
    master_volume = None; error_message = None
    try:
        speakers = AudioUtilities.GetSpeakers()
        if not speakers: error_message = "未能获取默认扬声器设备。"
        else:
            master_volume_interface = speakers.Activate(IAudioEndpointVolume._iid_, 0, None)
            if hasattr(master_volume_interface, 'SetMute') and hasattr(master_volume_interface, 'GetMute'):
                master_volume = master_volume_interface
            else: 
                 master_volume = master_volume_interface.QueryInterface(IAudioEndpointVolume)
    except AttributeError as ae: 
        app.logger.error(f"Error getting master volume control (AttributeError): {ae}")
        error_message = f"获取主音量控制时出错 (AttributeError): {str(ae)}"
    except Exception as e: 
        app.logger.error(f"Error getting master volume control: {e}")
        error_message = f"获取主音量控制时出错: {str(e)}"
    finally:
        if com_initialized_here and pythoncom:
            try: pythoncom.CoUninitialize()
            except Exception as e_un: app.logger.warning(f"Error during CoUninitialize: {e_un}")
    if error_message: return None, error_message
    if master_volume is None and not error_message: return None, "未能成功激活主音量控制接口。"
    return master_volume, None

def set_system_mute(mute_state: bool):
    master_volume, error = _get_master_volume_control()
    if error: return False, error
    try:
        master_volume.SetMute(1 if mute_state else 0, None)
        app.logger.info(f"System mute state set to: {mute_state}")
        return True, f"系统主音量静音状态已设置为 {'静音' if mute_state else '取消静音'}。"
    except Exception as e: 
        app.logger.exception("Error setting system mute state.")
        return False, f"设置系统静音时出错: {str(e)}"

def get_system_mute_status():
    master_volume, error = _get_master_volume_control()
    if error: return None, error
    try:
        muted = master_volume.GetMute()
        app.logger.debug(f"Current system mute status: {bool(muted)}")
        return bool(muted), "成功获取静音状态。"
    except Exception as e: 
        app.logger.exception("Error getting system mute status.")
        return None, f"获取系统静音状态时出错: {str(e)}"

@app.route('/api/audio/mute', methods=['POST', 'GET'])
@require_api_key
def audio_mute():
    if AudioUtilities is None: return jsonify({"status": "error", "action": "MUTE", "message": "音频控制功能不可用 (pycaw 未加载)。"}), 503
    success, message = set_system_mute(True)
    if success: return jsonify({"status": "success", "action": "MUTE", "audio_muted": True, "message": "系统音频已静音。", "details": message}), 200
    return jsonify({"status": "error", "action": "MUTE", "message": "静音系统音频失败。", "details": message}), 500

# ... (audio_unmute, audio_mute_toggle, audio_status 保持与之前类似, 确保日志记录)
@app.route('/api/audio/unmute', methods=['POST', 'GET'])
@require_api_key
def audio_unmute():
    if AudioUtilities is None: return jsonify({"status": "error", "action": "UNMUTE", "message": "音频控制功能不可用 (pycaw 未加载)。"}), 503
    success, message = set_system_mute(False)
    if success: return jsonify({"status": "success", "action": "UNMUTE", "audio_muted": False, "message": "系统音频已取消静音。", "details": message}), 200
    return jsonify({"status": "error", "action": "UNMUTE", "message": "取消系统音频静音失败。", "details": message}), 500

@app.route('/api/audio/mute/toggle', methods=['POST', 'GET'])
@require_api_key
def audio_mute_toggle():
    if AudioUtilities is None: return jsonify({"status": "error", "action": "TOGGLE_MUTE", "message": "音频控制功能不可用 (pycaw 未加载)。"}), 503
    current_mute_state, msg = get_system_mute_status()
    if current_mute_state is None: return jsonify({"status": "error", "action": "TOGGLE_MUTE", "message": "获取当前静音状态失败。", "details": msg}), 500
    new_mute_state = not current_mute_state; success, message = set_system_mute(new_mute_state)
    if success: return jsonify({"status": "success", "action": "TOGGLE_MUTE", "audio_muted": new_mute_state, "message": f"系统音频静音状态已切换为: {'静音' if new_mute_state else '取消静音'}", "details": message}), 200
    return jsonify({"status": "error", "action": "TOGGLE_MUTE", "message": "切换系统音频静音失败。", "details": message}), 500

@app.route('/api/audio/status', methods=['GET'])
@require_api_key
def audio_status():
    if AudioUtilities is None: return jsonify({"status": "error", "message": "音频控制功能不可用 (pycaw 未加载)。"}), 503
    muted, message = get_system_mute_status()
    if muted is not None: return jsonify({"status": "success", "audio_muted": muted, "message": "成功获取音频状态。", "details": message}), 200
    return jsonify({"status": "error", "message": "获取音频状态失败。", "details": message}), 500

# --- 状态（占位符） ---
@app.route('/api/monitor/<int:monitor_num>/status-placeholder', methods=['GET'])
@require_api_key
def monitor_status_placeholder(monitor_num):
    if not isinstance(monitor_num, int) or monitor_num <= 0: return jsonify({"status": "error", "message": "显示器编号必须是一个正整数。"}), 400
    return jsonify({"status": "info", "monitor_num": monitor_num, "message": "此接口为状态查询占位符。"}), 200


if __name__ == '__main__':
    # 启动前的检查和日志
    if not twinkle_tray_base_path_found:
        if shutil.which(twinkle_tray_base_path):
            app.logger.info(f"Twinkle Tray 将从 PATH 调用 ('{twinkle_tray_base_path}')。")
            twinkle_tray_base_path_found = True # 标记，避免重复检查
        else:
            app.logger.error(f"在预设路径及系统 PATH 中均未找到 Twinkle Tray ('{twinkle_tray_base_path}')。显示器亮度/VCP电源控制功能可能无法使用。")
    elif twinkle_tray_base_path_found:
         app.logger.info(f"Twinkle Tray 路径配置为: {twinkle_tray_base_path}")

    if AudioUtilities is None or IAudioEndpointVolume is None:
        app.logger.warning("音频控制功能将不可用 (pycaw 或其组件未能成功加载)。")
    if pythoncom is None:
        app.logger.warning("pythoncom 模块未加载 (尝试 'pip install pywin32')。COM 初始化可能无法进行，音频功能可能会受影响。")

    app.logger.info(f"Flask API 服务器正在启动 on http://{FLASK_HOST}:{FLASK_PORT} (Debug: {FLASK_DEBUG_MODE})")
    app.logger.info("请确保已安装所有依赖: pip install Flask python-dotenv pycaw pywin32 waitress")
    
    if FLASK_DEBUG_MODE:
        app.run(host=FLASK_HOST, port=FLASK_PORT, debug=True)
    else:
        from waitress import serve
        serve(app, host=FLASK_HOST, port=FLASK_PORT, threads=8) # threads 可以根据需要调整