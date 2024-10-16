import argparse
import configparser


def __parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-path", type=str, default="config.ini")
    # input
    parser.add_argument("--instruction", type=str, required=False)
    parser.add_argument("--action-file", type=str, required=False)
    # server
    parser.add_argument("--qwen", type=str, required=False)
    parser.add_argument("--internvl", type=str, required=False)
    parser.add_argument("--florence", type=str, required=False)
    # models
    parser.add_argument("--use-eval", type=str, required=False)
    parser.add_argument("--use-florence-only", type=str, required=False)
    # modules
    parser.add_argument("--use-memory", type=str, required=False)
    parser.add_argument("--use-reflection", type=str, required=False)
    parser.add_argument("--use-analysis", type=str, required=False)
    parser.add_argument("--use-open-app", type=str, required=False)
    # prompts
    parser.add_argument("--do-stop", type=str, required=False)
    parser.add_argument("--option", type=str, required=False)
    # android
    parser.add_argument("--adb-path", type=str, required=False)
    parser.add_argument("--aapt-path", type=str, required=False,
                        help="/path/to/android/sdk/build-tools/android-[version]/aapt")
    parser.add_argument("--emu-path", type=str, required=False)
    parser.add_argument("--device-type", type=str, choices=['emu', 'real'], required=False,
                        help="real: run test on real android device\n"
                             "\tRequires --device-id\n"
                             "emu: run test on emulator\n"
                             "\tRequires --avd-name and --device-id")
    parser.add_argument("--device-id", type=str, required=False)
    parser.add_argument("--avd-name", type=str, required=False)
    parser.add_argument("--run-apps-through-adb", action="store_true", required=False)
    parser.add_argument("--snapshot", type=str, required=False)
    # others
    parser.add_argument("--max-steps", type=str, required=False)
    parser.add_argument("--eval-save-folder", type=str, required=False)

    return parser.parse_args()


def __get_config_args() -> argparse.Namespace:
    args = __parse_args()
    config_ini = configparser.ConfigParser()
    config_ini.read(args.config_path)

    new_config = dict()
    new_config["input"] = __parse_config_section(
        config_ini,
        "Input",
        [
            "instruction",
            "action_file"
        ],
        args
    )
    new_config["server"] = __parse_config_section(
        config_ini,
        "Server",
        [
            "qwen",
            "internvl",
            "florence"
        ],
        args
    )
    new_config["models"] = __parse_config_section(
        config_ini,
        "Models",
        [
            "use_eval",
            "use_florence_only"
        ],
        args
    )
    new_config["modules"] = __parse_config_section(
        config_ini,
        "Modules",
        [
            "use_memory",
            "use_reflection",
            "use_analysis",
            "use_open_app"
        ],
        args
    )
    new_config["prompts"] = __parse_config_section(
        config_ini,
        "Prompts",
        [
            "do_stop",
            "option"
        ],
        args
    )
    new_config["android"] = __parse_config_section(
        config_ini,
        "Android",
        [
            "adb_path",
            "aapt_path",
            "emu_path",
            "device_type",
            "device_id",
            "avd_name",
            "snapshot",
            "run_apps_through_adb"
        ],
        args
    )
    new_config["other"] = __parse_config_section(
        config_ini,
        "Other",
        [
            "max_steps",
            "eval_save_folder"
        ],
        args
    )
    return argparse.Namespace(**new_config)


def __parse_config_section(config, section_name, list_of_values, args):
    section = dict()
    for value in list_of_values:
        # Recognize if boolean or not
        if isinstance(config.get(section_name, value), str) and \
                config.get(section_name, value).lower() in ['true', 'false', '1', '0']:
            config_value = config.getboolean(section_name, value)
        else:
            config_value = config.get(section_name, value)

        section[value] = __override_value_if_present(
            config_value,
            getattr(args, value)
        )
    return argparse.Namespace(**section)


def __override_value_if_present(value_to_override, new_value):
    return value_to_override if new_value is None else new_value


def get_config():
    return __get_config_args()
