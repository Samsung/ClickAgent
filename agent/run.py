import json
import os
import re
import subprocess
import time

from PIL import Image

import config_manager
from api_florence import create_local_florence_payload, query_florence
from api_internvl import create_internvl_payload, query_internvl
from api_qwen import query_qwen, create_qwen_payload_for_action
from chat_internvl import add_response, init_process_chat
from controller import AndroidDevice, AndroidEmulatorException, AdbException
from prompt import get_action_prompt, get_analysis_prompt, get_action_prompt_with_analysis, \
    get_memory_prompt, get_process_prompt, build_final_eval_v3_final_prompt_web, \
    build_final_eval_v3_final_prompt_general, build_init_eval_general, build_init_eval_web
from utils import draw_click, add_action, draw_rectangle


def take_screenshot(device, file_name, file_path) -> Image:
    os.makedirs(file_path, exist_ok=True)
    full_path = str(os.path.join(file_path, file_name))
    return device.get_screenshot(full_path)


def prepare_folders(configuration):
    os.makedirs(f"../output/action_logs", exist_ok=True)
    os.makedirs(f"../output/trajectories/{configuration.other.eval_save_folder}", exist_ok=True)
    os.makedirs(f"../output/eval_trajectories/", exist_ok=True)


def get_prompt(action_history, add_info, analysis_history, completed_requirements, config, instruction, keyboard,
               memory, summary_history, thought_history, use_open_app):
    if config.modules.use_analysis:
        prompt_action = get_action_prompt_with_analysis(
            instruction,
            keyboard,
            summary_history,
            action_history,
            thought_history,
            analysis_history,
            add_info,
            completed_requirements,
            memory,
            config.prompts.do_stop,
            config.prompts.option,
            use_open_app
        )
    else:
        prompt_action = get_action_prompt(
            instruction,
            keyboard,
            summary_history,
            action_history,
            thought_history,
            add_info,
            completed_requirements,
            memory,
            config.prompts.do_stop,
            config.prompts.option,
            use_open_app
        )
    return prompt_action


def run(config, and_device):
    if int(config.other.max_steps) < 1:
        return None

    prepare_folders(config)

    instruction = config.input.instruction
    action_path = config.input.action_file
    eval_save_folder = config.other.eval_save_folder
    thought_history = []
    summary_history = []
    action_history = []
    analysis_history = []
    summary = ""
    thought = ""
    is_success = False
    reflect_done = ""
    analysis = None
    description = ""
    answer = ""
    action = ""
    command = ""
    completed_requirements = ""
    memory = ""
    chat_action = None

    trajectory_log = {
        "intent": instruction,
        "steps": []
    }

    print(">>> Start evaluation: ", int(config.other.max_steps))

    add_info = (f"Change (brief description) to proper description of element in output. "
                f"Look on your history actions, when you are deciding about next action. "
                f"Do not use the same thoughts in the row. Avoid using the same output.")

    screenshots = []
    iteration = 0
    for iteration in range(int(config.other.max_steps)):
        use_open_app = and_device.is_home_screen()

        x, y = and_device.get_screen_size()
        tap_x, tap_y, lift_x, lift_y = -1, -1, -1, -1

        screenshots.append(take_screenshot(
            and_device,
            f"screenshot_{iteration}.jpg",
            f"../output/eval_trajectories/{eval_save_folder}/{action_path}/"
        ))

        start = time.time()

        prompt_action = get_prompt(
            action_history=action_history,
            add_info=add_info,
            analysis_history=analysis_history,
            completed_requirements=completed_requirements,
            config=config,
            instruction=instruction,
            keyboard=and_device.is_keyboard_open(),
            memory=memory,
            summary_history=summary_history,
            thought_history=thought_history,
            use_open_app=use_open_app
        )

        if not config.models.use_florence_only:
            output_action = query_qwen_llm(action_history, config, instruction, prompt_action, screenshots)

            print("Finished LLM Querying")
            action = output_action["action"]
            prev_command = command
            summary = output_action["summary"]
            thought = output_action["thought"]
            command = output_action["command"]
            is_success = output_action["success"]
            groundtruth = output_action["groundtruth"]
            reflect_done = output_action["reflection_status"]
            description = output_action["description"]
            save_to_logs = output_action["chat_action"]
            save_to_logs_eval = output_action["chat_eval"]
            answer = output_action["answer"]
            save_to_logs_description = output_action["chat_description"]

            action_log_name = f"../output/action_logs/{action_path}"
            add_action(action_log=action_log_name + "_action", chat=save_to_logs)
            add_action(action_log=action_log_name + "_eval", chat=save_to_logs_eval)
            add_action(action_log=action_log_name + "_description", chat=save_to_logs_description)
        else:
            payload = create_local_florence_payload(instruction, screenshots[-1])
            output_action = {"response": query_florence(payload=payload, ip=config.server.florence)}
            action = "click"
            summary = ""
            thought = ""
            command = ""
            is_success = ""
            groundtruth = ""
            prev_command = ""
            answer = ""
            description = ""
            reflect_done = ""

        # Action completed successfully. Exit
        if "failure" not in is_success:
            break

        if "go to app" in action.lower():
            action_go_to_app(action, and_device, config)
        elif "type" in action.lower():
            if not action_type(
                    android_device=and_device,
                    screenshots=screenshots,
                    output_action=output_action,
                    eval_save_folder=eval_save_folder,
                    action_path=action_path,
                    iteration=iteration,
                    instruction=instruction,
                    groundtruth=groundtruth
            ):
                continue
        elif "click" in action.lower():
            if not action_click(
                    and_device=and_device,
                    output_action=output_action,
                    screenshots=screenshots,
                    eval_save_folder=eval_save_folder,
                    action_path=action_path,
                    iteration=iteration,
                    instruction=instruction
            ):
                continue
            if and_device.is_keyboard_open():
                print('#' * 5 + "type action" + '#' * 5)
                and_device.type(groundtruth)
                command += f" and typed {groundtruth}"
        elif "swipe" in action.lower():
            print('#' * 5 + "swipe action" + '#' * 5)
            tap_x, tap_y, lift_x, lift_y = and_device.slide(action, x, y)
        elif "home" in action.lower():
            actions_home(and_device)
        elif "stop" in action.lower():
            actions_stop(action, answer, command, description, is_success, lift_x, lift_y, reflect_done, screenshots,
                         summary, tap_x, tap_y, thought, trajectory_log)
            break

        end = time.time()

        print("decision what to click", end - start)
        time.sleep(11)

        analysis = None
        if config.modules.use_analysis and iteration >= 1:
            try:
                print(">>> Start analysis module")
                analysis_prompt = get_analysis_prompt(instruction, prev_command, analysis_history)

                payload = create_internvl_payload(analysis_prompt, [screenshots[-2], screenshots[-1]])
                print("Before querying for analysis, prev_command: ", prev_command)
                analysis = query_internvl(payload, ip=config.server.internvl)["message"]["content"]
                print(">>> Analysis riasa: ", analysis)
                if analysis:
                    analysis = analysis.replace("Analysis:", "")
                    analysis_history.append(analysis)
                else:
                    print("!!! Analysis Error !!!")
                    analysis_history.append("")
                    analysis = "null"

            except Exception as e:
                print("!!! Analysis Exception !!! ->", e)
                analysis_history.append("")

        trajectory_log["steps"].append({
            "img": screenshots[-1].filename,
            "other": {
                "thought": thought,
                "summary": summary,
                "action": action,
                "command": command,
                "coordinates": [tap_x, tap_y, lift_x, lift_y],
                "status": is_success,
                "reflection_done": reflect_done,
                "analysis": analysis if analysis else "null",
                "description": description,
                "answer": answer
            }
        })

        thought_history.append(thought)
        summary_history.append(summary)
        action_history.append(command + " " + description)

        if config.modules.use_reflection:
            print(screenshots[-1].filename, "-" * 50)
            prompt_porcess = get_process_prompt(instruction, thought_history, summary_history, action_history,
                                                completed_requirements, add_info)
            chat_process = init_process_chat()
            payload = create_internvl_payload(prompt_porcess, [screenshots[-1]], chat_process)
            process_output = query_internvl(payload, ip=config.server.internvl)["message"]["content"]
            print(process_output)

            try:
                completed_requirements = re.search(r"Completed contents:(.*)", process_output).group(1).strip()
            except:
                pass
            add_response("assistant", process_output, chat_process)

        if config.modules.use_memory:
            insight = summary_history
            prompt_memory = get_memory_prompt(insight)

            payload = create_internvl_payload(prompt_memory, [screenshots[-1]], chat_action)
            chat_action = add_response("user", prompt_memory, chat_action)

            output_memory = query_internvl(payload=payload, ip=config.server.internvl)['message']['content'] + "\n"

            chat_action = add_response("assistant", output_memory, chat_action)

            output_memory = output_memory.split("### Important content ###")[-1].split("\n\n")[0].strip() + "\n"
            if "None" not in output_memory and output_memory not in memory:
                memory += output_memory

    screenshots.append(take_screenshot(
        and_device,
        f"{action_path}/screenshot_{iteration + 1}.jpg",
        f"../output/eval_trajectories/{eval_save_folder}/"))

    close_opened_screenshots(screenshots)

    trajectory_log["steps"].append({
        "img": screenshots[-1].filename,
        "other": {
            "thought": thought,
            "summary": summary,
            "action": action,
            "command": command,
            "coordinates": [-1, -1, -1, -1],
            "status": is_success,
            "reflection_done": reflect_done,
            "analysis": analysis if analysis else "null",
            "description": description,
            "answer": answer
        }
    })
    print(trajectory_log)
    update_trajectory_log(action_path, eval_save_folder, trajectory_log)

    return action_history


def query_qwen_llm(action_history, config, instruction, prompt_action, screenshots):
    print("Querying LLM -> screenshot file: ", screenshots[-1].filename)
    prompt_reflection = []
    prompt_init_chat = []
    prompt_reflection.append(build_final_eval_v3_final_prompt_web(instruction, action_history))
    prompt_reflection.append(build_final_eval_v3_final_prompt_general(instruction, action_history))
    prompt_init_chat.append(build_init_eval_web())
    prompt_init_chat.append(build_init_eval_general())
    payload = create_qwen_payload_for_action(prompt_action, screenshots[-1], instruction, action_history,
                                             config.models.use_eval, prompt_reflection, prompt_init_chat)
    print("Querying LLM #2")
    output_action = query_qwen(payload=payload, ip=config.server.qwen)
    return output_action


def close_opened_screenshots(screenshots):
    for screenshot in screenshots:
        screenshot.close()


def update_trajectory_log(action_path, eval_save_folder, trajectory_log):
    trajectory_log_path = f"../output/trajectories/{eval_save_folder}/trajectory_log_{action_path}.json"
    with open(trajectory_log_path, "a") as f:
        json.dump(trajectory_log, f, indent=4)
    print("Trajectory log and eval log saved successfully.")


def actions_stop(action, answer, command, description, is_success, lift_x, lift_y, reflect_done, screenshots, summary,
                 tap_x, tap_y, thought, trajectory_log):
    trajectory_log["steps"].append({
        "img": screenshots[-1].filename,
        "other": {
            "thought": thought,
            "summary": summary,
            "action": action,
            "command": command,
            "coordinates": [tap_x, tap_y, lift_x, lift_y],
            "status": is_success,
            "reflection_done": reflect_done,
            "description": description,
            "answer": answer
        }
    })
    print('#' * 5 + "stop action" + '#' * 5)


def actions_home(and_device):
    print('#' * 5 + "home action" + '#' * 5)
    and_device.home()


def action_go_to_app(action, and_device, config):
    print('#' * 5 + "go to app" + '#' * 5)
    print("ACTION: ", action.lower())
    app_name = action.lower().split("-").pop().strip()
    print("App name: ", app_name)
    if app_name:
        closest_app = and_device.find_closest_app_internvl(app_name, config.server.internvl)
        print("Closest app: ", closest_app)
    else:
        print("Something went wrong while extracting app name")
    time.sleep(3)


def action_type(android_device, screenshots, output_action, eval_save_folder, action_path, iteration, instruction,
                groundtruth):
    if not android_device.is_keyboard_open():
        print('#' * 5 + "click action" + '#' * 5)
        click_point = output_action["response"]
        print(">>> click point", click_point)

        if not click_point:
            return False

        draw_click(
            image=screenshots[-1],
            click_point=click_point,
            output_path=f"../output/eval_trajectories/{eval_save_folder}/{action_path}/screenshot_{iteration - 1}_click.png"
        )
        draw_rectangle(
            image=screenshots[-1],
            coordinates=output_action["bbox"],
            colour=(255, 0, 0),
            label=instruction
        )
        android_device.tap(x=click_point[0], y=click_point[1])
    print('#' * 5 + "type action" + '#' * 5)
    time.sleep(1)
    android_device.type(groundtruth)
    return True


def action_click(and_device, output_action, screenshots, eval_save_folder, action_path, iteration, instruction):
    print('#' * 5 + "click action" + '#' * 5)
    click_point = output_action["response"]
    print(">>> click point", click_point)

    if not click_point:
        return False

    draw_click(
        image=screenshots[-1],
        click_point=click_point,
        output_path=f"../output/eval_trajectories/{eval_save_folder}/{action_path}/screenshot_{iteration - 1}_click.png"
    )
    draw_rectangle(
        image=screenshots[-1],
        coordinates=output_action["bbox"],
        colour=(255, 0, 0),
        label=instruction
    )
    and_device.tap(x=click_point[0], y=click_point[1])
    time.sleep(4)
    return True


def get_android_device(configuration):
    android_cfg = configuration.android
    print("#" * 50)
    print(android_cfg.device_id)
    print("#" * 50)
    if configuration.android.device_type == "emu":
        print("Starting emulator android device", android_cfg.adb_path, android_cfg.run_apps_through_adb)
        new_device = AndroidDevice(
            device_id=android_cfg.device_id,
            is_emu=True,
            adb_path=android_cfg.adb_path,
            aapt_path=android_cfg.aapt_path,
            emu_path=android_cfg.emu_path,
            avd_name=android_cfg.avd_name,
            snapshot=android_cfg.snapshot,
            run_apps_adb=True

        )
    else:
        new_device = AndroidDevice(
            device_id=android_cfg.device_id,
            adb_path=android_cfg.adb_path,
            aapt_path=android_cfg.aapt_path,
            run_apps_adb=True
        )
    return new_device


def preconfigure_device(device):
    device.configure_chrome_startup()
    time.sleep(1)
    device.home()
    time.sleep(1)


if __name__ == "__main__":
    global_config = config_manager.get_config()
    android_device = None
    try:
        android_device = get_android_device(global_config)
        preconfigure_device(android_device)
        run(global_config, android_device)
    except (AndroidEmulatorException, AdbException) as e:
        print(e)
        print("Trying to reset ADB and Android device...")
        if android_device is not None:
            android_device.reset_adb()
            if android_device.is_emulator():
                android_device.kill_emulator()
        else:
            commands = [
                f"{global_config.android.adb_path} kill emu",
                f"{global_config.android.adb_path} kill-server",
                f"{global_config.android.adb_path} start-server",
            ]
            for command in commands:
                subprocess.run(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    encoding='utf-8'
                )
    except Exception as e:
        print(e)
    finally:
        if android_device and android_device.is_emulator():
            android_device.kill_emulator()
