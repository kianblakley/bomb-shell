import subprocess
import re
import json


class NiriClient:
    def __init__(self):
        pass

    def get_screen_size(self):
        try:
            output = subprocess.check_output(
                ["niri", "msg", "-j", "outputs"], text=True
            )
            outputs = json.loads(output)
            if outputs:
                                                                     
                first_output = list(outputs.values())[0]
                return [
                    first_output["logical"]["width"],
                    first_output["logical"]["height"],
                ]
        except Exception as e:
            print(f"Failed to get screen size from niri: {e}")
        return [1920, 1080]

    def get_outputs(self):
        try:
            output = subprocess.check_output(["niri", "msg", "outputs"], text=True)
        except Exception as e:
            print(f"Failed to get niri outputs: {e}")
            return []

        outputs = []
        current_output = None
        parsing_modes = False

        for line in output.splitlines():
            if line.startswith("Output"):
                name_match = re.search(r'"(.*?)"', line)
                id_match = re.search(r"\((.*?)\)", line)
                current_output = {
                    "name": name_match.group(1) if name_match else "Unknown",
                    "id": id_match.group(1) if id_match else "Unknown",
                    "modes": [],
                    "current_mode": "",
                    "current_scale": 1.0,
                    "vrr": "not supported",
                }
                outputs.append(current_output)
                parsing_modes = False
            elif "Current mode:" in line:
                current_output["current_mode"] = line.split(":")[1].strip()
            elif "Scale:" in line:
                try:
                    current_output["current_scale"] = float(line.split(":")[1].strip())
                except Exception:
                    current_output["current_scale"] = 1.0
            elif "Variable refresh rate:" in line:
                current_output["vrr"] = line.split(":")[1].strip()
            elif "Available modes:" in line:
                parsing_modes = True
            elif parsing_modes and line.startswith("    "):
                mode = line.strip()
                current_output["modes"].append(mode)
            elif parsing_modes and not line.startswith("    ") and line.strip() != "":
                parsing_modes = False

        return outputs

    def set_mode(self, output_id, mode_str):
        try:
                                                                                                   
            clean_mode = mode_str.split(" ")[0]
            subprocess.run(
                ["niri", "msg", "output", output_id, "mode", clean_mode], check=True
            )
            return True
        except Exception as e:
            print(f"Failed to set niri mode: {e}")
            return False

    def set_scale(self, output_id, scale_float):
        try:
            subprocess.run(
                ["niri", "msg", "output", output_id, "scale", str(scale_float)],
                check=True,
            )
            return True
        except Exception as e:
            print(f"Failed to set niri scale: {e}")
            return False

    def set_output_power(self, output_id, state: bool):
        try:
            action = "on" if state else "off"
            subprocess.run(["niri", "msg", "output", output_id, action], check=True)
            return True
        except Exception as e:
            print(f"Failed to set niri output power: {e}")
            return False
