import os
import re
import shutil
import time
import subprocess

from PIL import Image
import json

from api_internvl import create_internvl_payload, query_internvl
from prompt import get_relevant_app_prompt


def clone_avd(src_avd_name, tar_avd_name, android_avd_home):
    src_avd_dir = os.path.join(android_avd_home, src_avd_name + '.avd')
    tar_avd_dir = os.path.join(android_avd_home, tar_avd_name + '.avd')
    src_ini_file = os.path.join(android_avd_home, src_avd_name + '.ini')
    tar_ini_file = os.path.join(android_avd_home, tar_avd_name + '.ini')
    if not os.path.exists(tar_avd_dir):
        shutil.copytree(str(src_avd_dir), str(tar_avd_dir))

    with open(src_ini_file, 'r') as src_ini, open(tar_ini_file, 'w') as tar_ini:
        for line in src_ini:
            tar_ini.write(line.replace(src_avd_name, tar_avd_name))

    for ini_name in ['config.ini', 'hardware-qemu.ini']:
        ini_path = os.path.join(str(tar_avd_dir), str(ini_name))
        if os.path.exists(ini_path):
            # Update paths and AVD name/ID
            with open(ini_path, 'r') as file:
                lines = file.readlines()
            with open(ini_path, 'w') as file:
                for line in lines:
                    new_line = line.replace(src_avd_name, tar_avd_name)
                    file.write(new_line)

    snapshots_hw_ini = os.path.join(str(tar_avd_dir), 'snapshots', 'default_boot', 'hardware.ini')
    if os.path.exists(snapshots_hw_ini):
        # Update AVD name/ID
        with open(snapshots_hw_ini, 'r') as file:
            lines = file.readlines()
        with open(snapshots_hw_ini, 'w') as file:
            for line in lines:
                new_line = line.replace(src_avd_name, tar_avd_name)
                file.write(new_line)


class AndroidDevice:
    def __init__(self,
                 device_id,
                 adb_path="adb",
                 aapt_path="aapt",
                 is_emu=False,
                 android_avd_home=None,
                 source_avd_name=None,
                 avd_name=None,
                 snapshot=None,
                 emu_path=None,
                 run_apps_adb=True
                 ):
        self.device_id = device_id
        self.adb_path = adb_path
        self.aapt_path = aapt_path
        self.is_emu = False
        print("Android Device: ", is_emu, android_avd_home, avd_name)
        if is_emu:
            self.is_emu = True
            self.emu_process = None
            self.android_avd_home = android_avd_home
            self.source_avd_name = source_avd_name
            self.avd_name = avd_name
            self.snapshot = snapshot
            self.emu_path = emu_path
            self.start_emulator()
        # ensure adb daemon is running
        subprocess.run(
            f"{self.adb_path} devices",
            capture_output=True,
            text=True,
            shell=True,
            encoding='utf-8'
        )
        self.installed_apps_labels = None
        self.installed_apps_dict = None
        self.installed_apps = None
        if run_apps_adb:
            print("ANDROID DEVICE INIT APP LIST GET")
            self.installed_apps_dict, self.installed_apps_labels = self.get_app_list_json()

    def start_emulator(self):
        if not self.is_emu:
            return
        device_port = re.findall(r'\d+', self.device_id)[0]
        print("Starting emulator with: ", self.emu_path, " + ", self.avd_name, " + ", device_port)
        self.emu_process = subprocess.Popen(
            f"{self.emu_path} -avd {self.avd_name} -port {device_port} -snapshot {self.snapshot}"
            f" -no-window -no-audio -skip-adb-auth -no-boot-anim -gpu auto -no-snapshot-save",
            shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        self.wait_until_device_has_started()

    def kill_emulator(self):
        if not self.is_emu:
            return
        self.run_adb(f"emu kill")
        if self.emu_process is not None:
            self.emu_process.terminate()
            self.emu_process = None
        time.sleep(1)

    def restart_emulator(self):
        if not self.is_emu:
            return
        self.kill_emulator()
        self.start_emulator()

    def reboot_emulator(self):
        if not self.is_emu:
            return
        self.run_adb("-e reboot")
        self.wait_until_device_has_started()

    def is_emulator(self):
        return self.is_emu

    def wait_until_device_has_started(self):
        timeout = 0
        while timeout < 60:
            result = subprocess.run(
                f"{self.adb_path} -s {self.device_id} shell getprop init.svc.bootanim",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding='utf-8'
            ).stdout
            if "stopped\n" == result:
                time.sleep(2)  # wait home screen fully loaded
                break
            time.sleep(1)
            timeout += 1
        if timeout >= 60:
            raise AndroidEmulatorException("Device connection timeout")

    def reset_emulator(self):
        if not self.is_emu:
            return
        self.kill_emulator()
        try:
            cache_avd_path = os.path.join(self.android_avd_home, self.avd_name + ".avd")
            cache_avd_ini_path = os.path.join(self.android_avd_home, self.avd_name + ".ini")
            if os.path.exists(cache_avd_path):
                shutil.rmtree(cache_avd_path, ignore_errors=True)
            if os.path.exists(cache_avd_ini_path):
                os.remove(cache_avd_ini_path)
            time.sleep(2)
            # Clone the source AVD and start the emulator
            clone_avd(self.source_avd_name, self.avd_name, self.android_avd_home)
        except OSError as e:
            print(f"Failed to reset the emulator: {e}")
            import traceback
            print(traceback.format_exc())

    def reset_adb(self):
        subprocess.run(
            f"{self.adb_path} kill-server",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding='utf-8'
        )
        subprocess.run(
            f"{self.adb_path} start-server",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding='utf-8'
        )
        time.sleep(1)

    def run_adb(self, command) -> str:
        adb_command = f"{self.adb_path} -s {self.device_id} {command}"
        result = subprocess.run(
            adb_command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding='utf-8'
        ).stdout
        self.check_adb_answer(result)
        return result

    def check_adb_answer(self, result):
        if f"device '{self.device_id}' not found" in result \
                or "adb: device offline" in result:
            raise AdbException(f"Device disconnected. "
                               "Restart emulator / check USB/WIFI adb connection / restart adb server")

    def get_screen_size(self) -> tuple[int, int]:
        result = self.run_adb(f"shell wm size")
        resolution_line = result.strip().splitlines()[-1]
        width, height = map(int, resolution_line.split(' ')[-1].split('x'))
        return width, height

    def get_screenshot(self, file_path) -> Image:
        self.run_adb(f"exec-out screencap -p > {file_path}")
        Image.open(file_path, formats=["png"]).convert('RGB').save(file_path)
        return Image.open(file_path)

    def is_keyboard_open(self):
        result = self.run_adb(f"shell dumpsys input_method")
        keyboard_open = "mInputShown=true" in result or "isInputViewShown=true" in result

        return keyboard_open

    def tap(self, x, y):
        self.run_adb(f" shell input tap {x} {y}")
        time.sleep(1)

    def type(self, text):
        for _ in range(30):
            self.run_adb(f"shell input keyevent 67")

        text = text.replace("\\n", "_").replace("\n", "_")
        for char in text:
            if char == ' ':
                self.run_adb(f"shell input text %s")
            elif char == '_':
                self.run_adb(f"shell input keyevent 66")
            elif 'a' <= char <= 'z' or 'A' <= char <= 'Z' or char.isdigit():
                self.run_adb(f" shell input text {char}")
            elif char in '-.,!?@\'°/:;()':
                self.run_adb(f"shell input text \"{char}\"")
            else:
                self.run_adb(f"shell am broadcast -a ADB_INPUT_TEXT --es msg \"{char}\"")
        time.sleep(0.3)
        self.run_adb(f"shell input keyevent 66")
        time.sleep(0.5)

    def slide(self, action, x, y):
        print(">>> slide: ", action)
        if "bottom-to-up" in action:
            self.run_adb(f"shell input swipe {int(x / 2)} {int(y / 8)} {int(x / 2)} {int(7 * y / 8)} 500")
            return int(x / 2), int(y / 8), int(x / 2), int(7 * y / 8)
        elif "up-to-bottom" in action:
            self.run_adb(f"shell input swipe {int(x / 2)} {int(7 * y / 8)} {int(x / 2)} {int(y / 8)} 500")
            return int(x / 2), int(7 * y / 8), int(x / 2), int(y / 8)
        elif "right-to-left" in action:
            self.run_adb(f"shell input swipe {int(7 * x / 8)} {int(y / 2)} {int(x / 8)} {int(y / 2)} 500")
            return int(7 * x / 8), int(y / 2), int(x / 8), int(y / 2)
        elif "left-to-right" in action:
            self.run_adb(f"shell input swipe {int(x / 8)} {int(y / 2)} {int(7 * x / 8)} {int(y / 2)} 500")
            return int(x / 8), int(y / 2), int(7 * x / 8), int(y / 2)
        return 0, 0, 0, 0

    def back(self):
        self.run_adb(f"shell input keyevent KEYCODE_BACK")

    def home(self):
        print(">>> Go to home")
        self.run_adb(f"shell input keyevent KEYCODE_HOME")

    def is_home_screen(self):
        return "type=home" in self.run_adb(f"shell \"dumpsys activity activities | grep mLastFocusedRootTask\"")

    def kill_all_bg_activities(self):
        self.run_adb(f"shell am force-stop `{self.adb_path} shell dumpsys \"activity recents | grep -E "
                     f"'baseIntent.*cmp=' | sed -n 's/.*cmp=//;s/\\/.*//p' \"`")

    def configure_chrome_startup(self):
        print(">>> Configure chrome startup")
        time.sleep(2)
        self.run_adb(f"shell am start -n com.android.chrome/com.google.android.apps.chrome.Main")
        time.sleep(2)
        self.run_adb(f"shell am start -a android.intent.action.VIEW  -d 'https://google.com' --activity-clear-task")
        time.sleep(2)
        print(">>> Chrome configured")

    def run_app(self, app_id):
        print("Run app: ", app_id)
        self.run_adb(f"shell monkey -p {app_id} -c android.intent.category.LAUNCHER 1")

    def run_app_with_activity(self, app_id, activity_id):
        self.run_adb(f"shell am start -n {app_id}/{activity_id}")

    def get_application_list(self, renew=False) -> dict:
        if self.installed_apps is not None and not renew:
            return self.installed_apps

        installed_apps = dict()
        path_to_download_apk = './tmp_apk'

        packages = self.run_adb(f"shell cmd package list packages")
        package_list = packages.splitlines()
        for package in package_list:
            try:
                package_id = package.split(":")[1]

                package_info = self.run_adb(f"shell dumpsys package {package_id}")

                apk_path = re.search(r"(?<=path:).*\.apk", package_info).group().strip()

                activities = set()
                for match in re.findall(package_id + r".*Activity", package_info):
                    activities.add(match)
                if len(activities) == 0:
                    continue

                if not os.path.exists(path_to_download_apk):
                    os.makedirs(path_to_download_apk, exist_ok=True)
                apk_name = apk_path.split("/")[-1]
                try:
                    self.run_adb(f"pull {apk_path} {path_to_download_apk}")
                    apk_info = subprocess.run(
                        f"{self.aapt_path} dump badging {os.path.join(path_to_download_apk, apk_name)}",
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        encoding='utf-8'
                    ).stdout
                    self.check_adb_answer(apk_info)
                    search = re.search(r"(?<=application-label:).*", apk_info)
                    apk_label = search.group().strip().replace("'", "")
                except Exception:
                    continue
                finally:
                    os.remove(os.path.join(path_to_download_apk, apk_name))
                installed_apps[package_id] = {
                    "label": apk_label,
                    "activities": activities,
                    "apk_path": apk_path,

                }
            except Exception:
                continue
        self.installed_apps = installed_apps
        return self.installed_apps

    # DO NOT USE WITH EMULATOR
    # --cache-only does not work on emulators. Shell command will go to infinite loop
    def clear_app_cache(self, app_id):
        self.run_adb(f"shell pm clear --cache-only {app_id}")

    def get_app_list_json(self):
        with open("../apps.json", "r") as f:
            content = json.load(f)
            app_list, labels = [], []
            for key, value in content.items():
                app_list.append({"label": value["label"], "id": key})
                labels.append(value["label"])

            return app_list, labels

    def find_closest_app_internvl(self, app_name, ip_internvl):
        prompt = get_relevant_app_prompt(app_name, self.installed_apps_labels)
        payload = create_internvl_payload(prompt, [])
        try:
            analysis = query_internvl(payload, ip=ip_internvl)["message"]["content"]
            app = re.search(r"app:\s*(.*)", analysis).group(1)
            print("Application: ", app)
            app_id = [item["id"] for item in self.installed_apps_dict if item['label'].lower() == app.lower()]
            print("Found app id to launch: ", app_id[0])
            self.run_app(app_id[0])
            return app
        except Exception as e:
            print("Error launching app: ", e)
            return None


class AndroidEmulatorException(Exception):
    pass


class AdbException(Exception):
    pass
